# Label review — author notes vs independent labeller

Compared per case: outcome, record types, sources, required fields, `not_found` traps.
"Author" = `_authoring/<id>/notes.md` (agent A). "Labeller" = `cases/<id>/expected.yaml` (agent B,
who saw only the prompt and threads). Names that match through synonyms are not listed.
Decision ids (D1..) are for arbitration; `expected.yaml` is untouched until Jihad decides.

## Agreement (no action)
- Outcome agrees in all 12 cases (10 `ok`, 1 `needs_clarification`, 1 `unsupported`).
- Record types and sources agree in 10/12 cases (disagreements: D2, D3).
- `not_found` traps agree for vendor-invoices-payable (`po_number`), shipments-tracking (duty),
  frontend-hiring-pipeline (expected pay). Disagreement: D4.
- needs-attention-vague and project-profitability-unsupported agree. The labeller flags the latter
  as slightly unsure (a partial "revenue minus emailed costs" view); the prompt says "after all my costs".

## Disagreements that change scoring

### D1 — apartment-viewings: field type of `deposit`
Prompt: "...whether the agent said anything about a deposit."
- Author: `deposit` is `money`, found.
- Labeller: `deposit` is `string`, found (threads say "1 month", "5 weeks", "1,557 GBP", "one week's rent").
- Also: author requires `monthly_rent` and property `status` (enum) and viewing `status`; the labeller
  lists rent/status as optional (the prompt does not ask for them).

### D2 — client-pipeline-board: `thread` vs `extracted`
Prompt: "...client conversations laid out like a board..."
- Author: `client_conversation`, **source thread** (one card per thread).
- Labeller: `client`, **source extracted** (clients span several threads: Mei, Reed, Marini, Wright...).
  Labeller itself calls this "genuinely ambiguous".
- Required fields: author also requires `quoted_amount` (money) and `last_contact` (date); the labeller
  makes `quote_amount` optional since the prompt asks only for stages.

### D3 — tenant-repair-requests: `thread` vs `extracted`
Prompt: "Show me each repair issue and where it's at - new, someone's coming, sorted..."
- Author: `repair_request`, **source thread** (one card per reported issue/thread).
- Labeller: `repair_request`, **source extracted** (the same issue spans several threads: mould, sockets, boiler).
- Required fields: author also requires `tenant_name` and `unit`; labeller has only `description` + `status`
  (flat/tenant optional).

### D4 — tool-subscriptions-renewals: support of `user` ("who on the team actually uses it")
- Author: `user` is **not_found** (no systematic assignment; two staff mentions are partial).
- Labeller: `user` is **found**, sparse (Pixelforge: Mara and Jonas; Taskwise unused by Jonas).
- Author flagged this case as borderline. Affects the support-accuracy metric and whether the
  planner is expected to keep a "not found" field.

### D5 — support-needs-reply: is `status` required?
Prompt: "...which customer emails are still waiting for an answer from me and how long they've been waiting"
- Author: required `customer_name`, `status` (enum needs_reply / waiting_on_customer / resolved),
  a date or `waiting_days`, and `subject`.
- Labeller: required `customer` and `waiting_since` (date) only; `status`, `subject` optional
  ("only unanswered customer emails count" is treated as a filter, not a field).

### D6 — web-clients-projects-signoffs: required fields
- Author: `approval` requires `project`, `item`, `status`; `project` requires `status`; `client` requires `contact_email`.
  `project.value` found (agree).
- Labeller: `approval` requires `client` and `item` (`project`, `status` optional); `project` requires `client`,
  `name`, `value`; `client` only `name`.
- Both are unsure whether `approval` is a type or a field on `project`; both chose a type.
- Link field of `approval` to its parent differs (`project` vs `client`); with the current scorer a
  planner that links to the other one counts one required field missing and one extra.

## Minor differences in required vs optional (author required, labeller optional)
- shipments-tracking: `status` (author: implied by "still on its way"; not asked in prompt).
- inbox-urgency-kanban: `subject` (author required; prompt asks for urgency columns and "who is asking").
- frontend-hiring-pipeline: candidate `email`; interview `interviewer`/format.
- vendor-invoices-payable: vendor `contact_email`; invoice `status`.

## Decisions requested
For each of D1-D6, say which side to adopt (or a custom answer). For the minor list, say whether to keep
the labeller's version (default) or promote any to required.
