"""Planner data contracts: the thread input and the `Schema` the planner outputs.

Vocabulary: workspace, prompt, schema, record type, record, field, thread, message.
A `Schema` is later stored in `workspaces.config`. Links between record types are plain
matching values (e.g. `project.client` holds the same string as `client.name`), never
references.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class FieldType(StrEnum):
    string = "string"
    number = "number"
    money = "money"
    date = "date"
    boolean = "boolean"
    enum = "enum"


class Origin(StrEnum):
    """Why a field is in the schema.

    explicit = asked for in the prompt, or required by what the prompt asks to see
               (e.g. a status/stage for a board).
    inferred = the planner's own guess from the prompt.
    observed = added because the sampled threads show it and it serves the prompt.
    """

    explicit = "explicit"
    inferred = "inferred"
    observed = "observed"


class Support(StrEnum):
    """Does the information appear in the sampled threads?"""

    found = "found"
    not_found = "not_found"


class Source(StrEnum):
    """How records of a record type come about.

    thread    = one record per thread; identity is the thread id.
    extracted = records assembled from facts across messages (e.g. invoices).
    """

    thread = "thread"
    extracted = "extracted"


class Field(BaseModel):
    name: str  # snake_case, unique within its record type
    label: str  # UI name, e.g. "Due date"
    description: str  # one sentence = the extraction instruction
    type: FieldType
    allowed_values: list[str] | None  # enum only: 2-6 snake_case values from the threads' wording
    origin: Origin
    support: Support
    justification: str | None  # required iff origin == observed: how it serves the prompt


class RecordType(BaseModel):
    name: str  # snake_case singular, e.g. "invoice"
    label: str  # UI name, e.g. "Invoices"
    description: str  # what one record is
    source: Source
    identity: str | None  # extracted only: one sentence, how to tell two mentions are the same
    fields: list[Field]


class Schema(BaseModel):
    version: int = 1
    outcome: Literal["ok", "needs_clarification", "unsupported"]
    user_message: str | None  # required when outcome != ok, shown to the user
    scope: str | None  # what the whole workspace covers
    record_types: list[RecordType]  # empty unless outcome == ok
    unresolved: list[str]  # internal diagnostics


class Message(BaseModel):
    message_id: str
    sender: str
    to: list[str]
    date: datetime
    subject: str
    body: str
    attachments: list[str] = []


class Thread(BaseModel):
    thread_id: str
    messages: list[Message]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class PlanResult:
    schema: Schema | None  # None if still invalid after the retry
    valid_first_try: bool
    attempts: int
    errors: list[str]  # validator errors of the last attempt (empty when valid)
    usage: Usage
    latency_ms: int
    raw_responses: list[str]
