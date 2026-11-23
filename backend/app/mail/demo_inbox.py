"""Write synthetic threads into the demo inbox over IMAP (admin "Demo inbox" only).

This is the only code in Demux that writes mail, and it only ever touches the demo inbox
configured by TEST_GMAIL / TEST_GMAIL_PASSWORD (a Gmail app password). Users'
own Gmail stays read-only through OAuth; this never uses their tokens.

- `append_threads`: IMAP APPEND, so nothing is sent. Incoming messages go to INBOX, the
  owner's replies to the Sent mailbox; Gmail threads them by `References` and subject.
  The internal date is the message date, so Gmail search (`after:`) sees the past dates.
- Every message carries `X-Demux-Demo: <seed id>` and the Gmail label "Demux demo"
  (set from the APPENDUID response); `remove_demo_messages` moves everything under that
  label to Trash.

imaplib is blocking: callers run these functions in a thread.
"""

import imaplib
import re
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid

DEMO_HEADER = "X-Demux-Demo"
DEMO_LABEL = "Demux demo"
_APPENDUID_RE = re.compile(rb"APPENDUID \d+ (\d+)")
_LIST_RE = re.compile(r'\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$')


class DemoInboxError(Exception):
    pass


@dataclass
class DemoMessage:
    from_name: str
    from_email: str
    to_name: str
    to_email: str
    subject: str
    body: str
    date: datetime
    outgoing: bool  # written by the inbox owner (goes to Sent)
    seen: bool = True


def _quote(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _special_folders(imap: imaplib.IMAP4_SSL) -> dict[str, str]:
    """Special-use folder names (\\Sent, \\All, \\Trash): they are localized per account."""
    status, lines = imap.list()
    if status != "OK":
        return {}
    out: dict[str, str] = {}
    for raw in lines or []:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        m = _LIST_RE.search(line)
        if not m:
            continue
        name = m.group("name").strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1]
        for flag in m.group("flags").split():
            if flag in ("\\Sent", "\\All", "\\Trash"):
                out[flag] = name
    return out


def _connect(host: str, email: str, password: str) -> imaplib.IMAP4_SSL:
    try:
        imap = imaplib.IMAP4_SSL(host, timeout=30)
        imap.login(email, password)
    except imaplib.IMAP4.error as e:
        raise DemoInboxError(
            "The demo inbox rejected the login. Check TEST_GMAIL and "
            "TEST_GMAIL_PASSWORD (a Google app password, not the account password)."
        ) from e
    except OSError as e:
        raise DemoInboxError(f"Could not reach {host} ({type(e).__name__}).") from e
    return imap


def build_threads(
    threads: list[list[DemoMessage]], seed_id: str, domain: str = "demo.usedemux.com"
) -> list[tuple[EmailMessage, DemoMessage]]:
    """MIME messages with Message-ID / In-Reply-To / References chains per thread."""
    out = []
    for thread in threads:
        ids: list[str] = []
        for i, m in enumerate(thread):
            msg = EmailMessage()
            msg["From"] = formataddr((m.from_name, m.from_email))
            msg["To"] = formataddr((m.to_name, m.to_email))
            msg["Subject"] = m.subject if i == 0 else f"Re: {m.subject}"
            msg["Date"] = format_datetime(m.date)
            msg_id = make_msgid(domain=domain)
            msg["Message-ID"] = msg_id
            if ids:
                msg["In-Reply-To"] = ids[-1]
                msg["References"] = " ".join(ids)
            msg[DEMO_HEADER] = seed_id
            msg.set_content(m.body)
            ids.append(msg_id)
            out.append((msg, m))
    return out


def append_threads(
    host: str, email: str, password: str, threads: list[list[DemoMessage]], seed_id: str
) -> int:
    """APPEND every message; returns how many were stored."""
    imap = _connect(host, email, password)
    try:
        sent = _special_folders(imap).get("\\Sent", "[Gmail]/Sent Mail")
        imap.create(_quote(DEMO_LABEL))  # fails harmlessly when it exists
        uids: dict[str, list[bytes]] = {}
        stored = 0
        for msg, meta in build_threads(threads, seed_id):
            folder = sent if meta.outgoing else "INBOX"
            flags = "(\\Seen)" if meta.seen else "()"
            status, data = imap.append(
                _quote(folder), flags, imaplib.Time2Internaldate(meta.date), msg.as_bytes()
            )
            if status != "OK":
                raise DemoInboxError(f"The demo inbox refused a message ({status}).")
            stored += 1
            m = _APPENDUID_RE.search(b" ".join(d for d in data or [] if isinstance(d, bytes)))
            if m:
                uids.setdefault(folder, []).append(m.group(1))
        for folder, folder_uids in uids.items():
            if imap.select(_quote(folder))[0] == "OK":
                uid_set = b",".join(folder_uids).decode()
                imap.uid("STORE", uid_set, "+X-GM-LABELS", f"({_quote(DEMO_LABEL)})")
        return stored
    finally:
        try:
            imap.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def remove_demo_messages(host: str, email: str, password: str) -> int:
    """Move every message carrying the demo header to Trash. Returns how many."""
    imap = _connect(host, email, password)
    try:
        trash = _special_folders(imap).get("\\Trash", "[Gmail]/Trash")
        if imap.select(_quote(DEMO_LABEL))[0] != "OK":
            return 0  # the label does not exist: nothing was ever seeded
        status, data = imap.uid("SEARCH", None, "ALL")
        uids = (data[0] or b"").split() if status == "OK" and data else []
        if not uids:
            return 0
        # Gmail: copying a message to Trash moves it there (deleted after 30 days).
        status, _ = imap.uid("COPY", b",".join(uids).decode(), _quote(trash))
        if status != "OK":
            raise DemoInboxError("Could not move the demo threads to Trash.")
        return len(uids)
    finally:
        try:
            imap.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
