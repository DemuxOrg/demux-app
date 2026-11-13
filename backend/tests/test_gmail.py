"""GmailMailbox against a mocked Gmail REST API (no network)."""

import base64

import httpx
import pytest

from app.mail.base import ReconnectRequired
from app.mail.gmail import GmailMailbox
from tests.helpers import dt


def b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def msg(mid: str, ms: int, subject: str, body: str) -> dict:
    return {
        "id": mid,
        "internalDate": str(ms),
        "snippet": body[:20],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "Shop <s@shop.example>"},
                {"name": "To", "value": "me@x.example"},
                {"name": "Subject", "value": subject},
            ],
            "body": {"data": b64(body)},
        },
    }


THREADS = {
    "aaa111": [
        msg("m1", 1760000000000, "Order 1", "first"),
        msg("m2", 1760100000000, "Re: Order 1", "second"),
    ],
    "bbb222": [msg("m3", 1760200000000, "Order 2", "third")],
}


class Tokens:
    def __init__(self):
        self.calls = []

    async def get(self, force_refresh=False):
        self.calls.append(force_refresh)
        return "fresh" if force_refresh else "stale"


def handler(seen: list):
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers["Authorization"] != "Bearer fresh":
            return httpx.Response(401)
        path = request.url.path
        if path.endswith("/threads"):
            return httpx.Response(200, json={"threads": [{"id": t} for t in THREADS]})
        tid = path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"id": tid, "messages": THREADS[tid]})

    return handle


async def test_search_refreshes_token_and_builds_summaries():
    seen: list = []
    tokens = Tokens()
    box = GmailMailbox(tokens, transport=httpx.MockTransport(handler(seen)))
    hits = await box.search("order", max_results=10, after=dt("2026-01-01T00:00:00Z"))
    await box.aclose()
    assert [h.thread_id for h in hits] == ["aaa111", "bbb222"]
    assert hits[0].message_count == 2 and hits[0].subject == "Order 1"
    assert True in tokens.calls  # refreshed after the 401
    q = seen[1].url.params["q"]
    assert q.startswith("(order)") and "after:" in q


async def test_get_thread_parses_and_sorts():
    box = GmailMailbox(Tokens(), transport=httpx.MockTransport(handler([])))
    thread = await box.get_thread("aaa111")
    await box.aclose()
    assert [m.body for m in thread.messages] == ["first", "second"]
    assert thread.messages[0].to == ["me@x.example"]


async def test_persistent_401_means_reconnect():
    class Bad(Tokens):
        async def get(self, force_refresh=False):
            return "stale"

    box = GmailMailbox(Bad(), transport=httpx.MockTransport(handler([])))
    with pytest.raises(ReconnectRequired):
        await box.get_thread("aaa111")
    await box.aclose()
