# Labelling guide — writing `expected.yaml`

You label a planner benchmark case from its **prompt** and its **threads** alone. The file
format is in `FORMAT.md`. You see `request.yaml` (the prompt) and `threads.json`.

## What the planner does

Given a user's prompt and a sample of their email threads, the planner designs a **schema**
for a **workspace** (a structured, refreshable view of the user's email). It does not extract
any values; it only decides *what* to extract.

- A **record type** is a kind of item shown in the workspace (e.g. `invoice`, `client`).
- A **record** is one instance of it. A **field** is one attribute of a record type.
- A **thread** is an email conversation made of **messages**.

### Outcome
- `ok`: a concrete record type can be named from the prompt and the information can come from email.
- `needs_clarification`: the prompt is too vague to name any concrete record type.
- `unsupported`: the information cannot come from email (e.g. needs accounting data).

### Source (per record type)
- `thread`: one thread = one item the user wants to see (e.g. "my client emails as a board").
- `extracted`: items are assembled from facts across messages or threads (e.g. invoices).

### Field origin and support
- Origin `explicit`: asked for in the prompt, or required by what the prompt asks to see
  (e.g. a status or stage for a board). `inferred`: the planner's own guess. `observed`: shown
  by the threads and serves the prompt.
- Support `found`: the information appears in the threads. `not_found`: it appears in none.

## Rules the correct schema follows
1. Decide the outcome first.
2. As many record types as the prompt needs, and no more.
3. `thread` when one thread = one item; `extracted` when assembled across messages/threads.
4. The prompt decides record types and explicit fields. Threads never remove an explicit
   field: if the information is absent from every thread, keep it with `support: not_found`.
5. Threads supply enum values (2-6, from their wording) and observed fields that serve the prompt.
6. Fields the planner merely guessed and the threads do not show are dropped.
7. Threads unrelated to the prompt (noise) never change the record types.
8. When record types relate, the child has a plain string field whose values match the
   parent's naming field (e.g. `project.client` vs `client.name`). No references.

## How to fill `expected.yaml`

1. Read the prompt. Decide `outcome`. If not `ok`, write only `outcome` and `notes`; stop.
2. List the record types the prompt needs. Give each a snake_case singular `name`, a few
   `synonyms`, and its `source`.
3. `required_fields`: every field the prompt asks for explicitly or needs to show (including
   the linking field of a child record type, and a status/stage for boards). Give `type`
   and `support` by checking the threads: `found` only if the information really appears.
4. `optional_fields`: reasonable extras the threads show that would not be wrong to include.
5. `forbidden_fields` / `forbidden_record_types`: things that would be clearly wrong (fields
   about unrelated noise threads, record types the prompt never asked for).
6. `notes`: one line on traps you noticed (missing data, messy wording, noise).

Label what the threads and prompt justify. Do not label from how you imagine a model would
answer, and do not pad required fields.
