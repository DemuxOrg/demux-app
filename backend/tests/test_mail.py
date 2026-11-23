"""FakeMailbox search semantics and time cutoff, TimeBoxedMailbox, cleaning, Gmail parsing."""

import base64

from app.mail.clean import clean_body, html_to_text
from app.mail.fake import FakeMailbox, TimeBoxedMailbox
from app.mail.gmail import parse_message
from tests.helpers import SMALL_MAILBOX, dt


async def _subjects(box, q, **kw):
    return sorted(s.subject for s in await box.search(q, max_results=50, **kw))


async def test_plain_terms_are_anded_and_case_insensitive():
    box = FakeMailbox.from_file(SMALL_MAILBOX)
    assert await _subjects(box, "ORDER chair") == ["Order #A-1042 confirmed"]


async def test_from_subject_or_and_phrase():
    box = FakeMailbox.from_file(SMALL_MAILBOX)
    assert await _subjects(box, "from:gadgethub.example subject:digest") == [
        "Weekly digest: new gadgets"
    ]
    assert len(await box.search("shipped OR delivered")) == 2
    assert await _subjects(box, '"office chair"') == ["Order #A-1042 confirmed"]
    assert len(await box.search("(lamp OR charger) total")) == 2
    assert len(await box.search("{lamp charger} total")) == 2


async def test_negation_and_ignored_operators():
    box = FakeMailbox.from_file(SMALL_MAILBOX)
    hits = await _subjects(box, "order -from:news label:inbox category:primary")
    assert "Autumn sale: 30% off lamps" not in hits
    assert "Order #A-1042 confirmed" in hits


async def test_after_before_and_now_cutoff():
    box = FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-16T00:00:00Z"))
    # The delivered message (2026-10-21) is hidden by `now`.
    assert await _subjects(box, "delivered") == []
    assert await _subjects(box, "order", after=dt("2026-10-11T00:00:00Z")) == [
        "Order #A-1042 confirmed",
        "Weekly digest: new gadgets",
        "dinner saturday?",
    ]
    assert len(await box.search("order before:2026/10/02")) == 1
    box.now = dt("2026-10-22T00:00:00Z")
    assert await _subjects(box, "delivered") == ["Order #A-1042 delivered"]


async def test_timeboxed_hides_later_messages():
    inner = FakeMailbox.from_file(SMALL_MAILBOX)
    box = TimeBoxedMailbox(inner, now=dt("2026-10-02T00:00:00Z"))
    hits = await box.search("A-1001")
    assert len(hits) == 1 and hits[0].message_count == 1
    thread = await box.get_thread(hits[0].thread_id)
    assert len(thread.messages) == 1


def test_clean_drops_quotes_and_signature():
    body = "Thanks, paid today.\n\nOn Mon, Oct 1, 2026 Bob wrote:\n> old stuff\n> more\n"
    assert clean_body(body) == "Thanks, paid today."
    assert clean_body("Hello\n-- \nBob\nCEO") == "Hello"
    assert clean_body("a\n\n\n   b") == "a b"


def test_html_to_text():
    assert html_to_text("<style>x{}</style><p>Hi&nbsp;<b>there</b></p><br>ok") == "Hi there\nok"


def test_parse_gmail_message_prefers_plain_and_lists_attachments():
    def b64(s):
        return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

    raw = {
        "id": "18c0000000000001",
        "internalDate": "1760000000000",
        "payload": {
            "headers": [
                {"name": "From", "value": "A <a@x.example>"},
                {"name": "To", "value": "B <b@x.example>, c@x.example"},
                {"name": "Subject", "value": "Hi"},
            ],
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": b64("plain body")}},
                        {"mimeType": "text/html", "body": {"data": b64("<p>html</p>")}},
                    ],
                },
                {"mimeType": "application/pdf", "filename": "inv.pdf", "body": {}},
            ],
        },
    }
    m = parse_message(raw)
    assert m.body == "plain body"
    assert m.to == ["b@x.example", "c@x.example"]
    assert m.attachments == ["inv.pdf"]
    raw["payload"]["parts"][0]["parts"].pop(0)
    assert parse_message(raw).body == "html"
