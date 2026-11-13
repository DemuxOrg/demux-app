"""Mailbox interface shared by Gmail, the fake mailbox and the time-boxed wrapper.

`Mailbox` is the only thing the agent knows about mail: search for threads and read a
thread. Implementations: `gmail.GmailMailbox` (real), `fake.FakeMailbox` (tests, CLI,
eval scenarios), `fake.TimeBoxedMailbox` (replay).
"""

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class ThreadSummary(BaseModel):
    thread_id: str
    subject: str
    senders: list[str]
    last_date: datetime
    message_count: int
    snippet: str


class Message(BaseModel):
    message_id: str
    sender: str
    to: list[str] = []
    date: datetime
    subject: str
    body: str
    attachments: list[str] = []


class Thread(BaseModel):
    thread_id: str
    messages: list[Message]


class Mailbox(Protocol):
    async def search(
        self,
        query: str,
        max_results: int = 25,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[ThreadSummary]: ...

    async def get_thread(self, thread_id: str) -> Thread: ...


class MailboxError(Exception):
    """A mailbox call failed for a reason the agent cannot fix."""


class ReconnectRequired(MailboxError):
    """The user's Google token is invalid or revoked; they must sign in again."""
