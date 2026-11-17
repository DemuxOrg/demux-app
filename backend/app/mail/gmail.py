"""Gmail mailbox (read-only) over the Gmail REST API v1 with httpx.

- `search`: `users.threads.list` with `q` (plus `after:`/`before:` as Unix seconds), then
  `users.threads.get?format=metadata` per thread for the summary.
- `get_thread`: `users.threads.get?format=full`; body is text/plain, falling back to
  stripped text/html. Attachments: file names only.

Access tokens come from a provider with `get(force_refresh=False)`; on a 401 the token is
refreshed once. Never logs content.
"""

import asyncio
import base64
import logging
from datetime import UTC, datetime
from email.utils import getaddresses
from typing import Any, Protocol

import httpx

from app.mail.base import MailboxError, Message, ReconnectRequired, Thread, ThreadSummary
from app.mail.clean import html_to_text

logger = logging.getLogger(__name__)

API = "https://gmail.googleapis.com/gmail/v1/users/me"


class TokenProvider(Protocol):
    async def get(self, force_refresh: bool = False) -> str: ...


def _b64(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _walk(part: dict[str, Any], plain: list[str], htmls: list[str], files: list[str]) -> None:
    mime = part.get("mimeType", "")
    body = part.get("body", {}) or {}
    if part.get("filename"):
        files.append(part["filename"])
    elif mime == "text/plain" and body.get("data"):
        plain.append(_b64(body["data"]))
    elif mime == "text/html" and body.get("data"):
        htmls.append(_b64(body["data"]))
    for sub in part.get("parts", []) or []:
        _walk(sub, plain, htmls, files)


def parse_message(raw: dict[str, Any]) -> Message:
    payload = raw.get("payload", {})
    headers = _headers(payload)
    plain: list[str] = []
    htmls: list[str] = []
    files: list[str] = []
    _walk(payload, plain, htmls, files)
    body = "\n".join(plain).strip() or html_to_text("\n".join(htmls))
    if not body:
        body = raw.get("snippet", "")
    to = [addr for _, addr in getaddresses([headers.get("to", "")]) if addr]
    date = datetime.fromtimestamp(int(raw.get("internalDate", "0")) / 1000, tz=UTC)
    return Message(
        message_id=raw["id"],
        sender=headers.get("from", ""),
        to=to,
        date=date,
        subject=headers.get("subject", ""),
        body=body,
        attachments=files,
    )


class GmailMailbox:
    def __init__(
        self,
        tokens: TokenProvider,
        *,
        concurrency: int = 8,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._tokens = tokens
        self._sem = asyncio.Semaphore(concurrency)
        self._client = httpx.AsyncClient(timeout=30, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | list[tuple[str, Any]]) -> Any:
        async with self._sem:
            for attempt in range(3):
                token = await self._tokens.get(force_refresh=attempt == 1)
                try:
                    resp = await self._client.get(
                        f"{API}{path}", params=params, headers={"Authorization": f"Bearer {token}"}
                    )
                except httpx.TransportError as e:
                    if attempt == 2:
                        raise MailboxError("Gmail is unreachable") from e
                    await asyncio.sleep(1 + attempt)
                    continue
                if resp.status_code == 401:
                    if attempt >= 1:
                        raise ReconnectRequired("gmail rejected the token")
                    continue
                if resp.status_code == 404:
                    raise MailboxError("not found")
                if resp.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                if resp.status_code == 403:
                    if "ratelimit" in resp.text.lower().replace("_", ""):
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    raise ReconnectRequired("gmail access denied (scope missing?)")
                resp.raise_for_status()
                return resp.json()
            raise MailboxError(f"Gmail request failed ({path.split('/')[1]})")

    async def search(
        self,
        query: str,
        max_results: int = 25,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[ThreadSummary]:
        ids = await self.search_ids(query, max_results, after, before)
        summaries = await asyncio.gather(*(self._summary(t) for t in ids))
        return [s for s in summaries if s is not None]

    async def search_ids(
        self,
        query: str,
        max_results: int = 25,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[str]:
        """Thread ids only (newest first), without fetching metadata."""
        q = f"({query})" if query.strip() else ""
        if after:
            q += f" after:{int(after.timestamp())}"
        if before:
            q += f" before:{int(before.timestamp())}"
        ids: list[str] = []
        page_token = None
        while len(ids) < max_results:
            params: dict[str, Any] = {"q": q, "maxResults": min(100, max_results - len(ids))}
            if page_token:
                params["pageToken"] = page_token
            body = await self._get("/threads", params)
            ids += [t["id"] for t in body.get("threads", [])]
            page_token = body.get("nextPageToken")
            if not page_token:
                break
        return ids[:max_results]

    async def _summary(self, thread_id: str) -> ThreadSummary | None:
        params = [
            ("format", "metadata"),
            ("metadataHeaders", "From"),
            ("metadataHeaders", "Subject"),
        ]
        try:
            body = await self._get(f"/threads/{thread_id}", params)
        except MailboxError:
            return None
        msgs = body.get("messages", [])
        if not msgs:
            return None
        senders: list[str] = []
        for m in msgs:
            sender = _headers(m.get("payload", {})).get("from", "")
            if sender and sender not in senders:
                senders.append(sender)
        last = msgs[-1]
        return ThreadSummary(
            thread_id=thread_id,
            subject=_headers(msgs[0].get("payload", {})).get("subject", ""),
            senders=senders[:5],
            last_date=datetime.fromtimestamp(int(last.get("internalDate", "0")) / 1000, tz=UTC),
            message_count=len(msgs),
            snippet=last.get("snippet", ""),
        )

    async def get_thread(self, thread_id: str) -> Thread:
        body = await self._get(f"/threads/{thread_id}", {"format": "full"})
        messages = [parse_message(m) for m in body.get("messages", [])]
        messages.sort(key=lambda m: m.date)
        return Thread(thread_id=thread_id, messages=messages)
