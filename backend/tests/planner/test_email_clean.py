from datetime import UTC, datetime

from app.pipeline.email_clean import clean_thread
from app.pipeline.planner.models import Message, Thread


def one(body, **kw):
    m = Message(
        message_id=kw.get("message_id", "m1"),
        sender="Ana <ana@acme.example>",
        to=["me@example.com"],
        date=datetime(2026, 3, 4, 9, 15, tzinfo=UTC),
        subject="Invoice 2041",
        body=body,
        attachments=["inv.pdf"],
    )
    return Thread(thread_id="t1", messages=[m])


def body_of(body):
    return clean_thread(one(body)).messages[0].body


def test_drops_quoted_lines():
    out = body_of("Thanks, paid.\n> Please pay invoice 2041\n> by Friday\nBest")
    assert "Please pay" not in out and "Friday" not in out
    assert "Thanks, paid." in out and "Best" in out


def test_drops_on_wrote_block():
    out = body_of(
        "Will do.\n\nOn Tue, Mar 3, 2026 at 10:00 AM Ana <ana@acme.example> wrote:\n"
        "> older text\n> more older text\n"
    )
    assert "Will do." in out
    assert "wrote" not in out and "older text" not in out


def test_drops_on_wrote_block_wrapped_over_two_lines():
    out = body_of(
        "Yes.\n\nOn Tue, Mar 3, 2026 at 10:00 AM, Ana Ruiz\n<ana@acme.example> wrote:\n> hi\n"
    )
    assert out.strip() == "Yes."


def test_drops_signature_after_dash_dash_space():
    out = body_of("Invoice attached.\n-- \nAna Ruiz\nAcme Supplies\n+34 600 000 000")
    assert "Invoice attached." in out
    assert "Ana Ruiz" not in out and "Acme" not in out and "600" not in out


def test_dash_dash_without_trailing_space_is_not_checked_strictly():
    # only the exact `-- ` marker is documented; plain text containing "--" inside a line stays
    out = body_of("Total -- 100 EUR\nDue 15 March")
    assert "Total -- 100 EUR" in out and "Due 15 March" in out


def test_collapses_whitespace():
    out = body_of("Hello    there,\n\n\n\n   the   invoice  is\t\tattached.   \n\n\n")
    assert "    " not in out and "\n\n\n" not in out and "\t" not in out
    assert out == out.strip()
    assert "Hello there," in out and "the invoice is attached." in out


def test_keeps_metadata():
    t = one("hi\n> quoted")
    out = clean_thread(t)
    m, o = t.messages[0], out.messages[0]
    assert out.thread_id == t.thread_id
    assert (o.message_id, o.sender, o.to, o.date, o.subject, o.attachments) == (
        m.message_id,
        m.sender,
        m.to,
        m.date,
        m.subject,
        m.attachments,
    )


def test_does_not_mutate_input_and_handles_all_messages():
    t = one("hi\n> quoted")
    t.messages.append(t.messages[0].model_copy(update={"message_id": "m2", "body": "yo\n> q"}))
    out = clean_thread(t)
    assert t.messages[0].body == "hi\n> quoted"
    assert [m.body.strip() for m in out.messages] == ["hi", "yo"]


def test_plain_body_unchanged_in_content():
    assert body_of("Invoice 2041 is due 15 March.") == "Invoice 2041 is due 15 March."
