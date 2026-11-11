# Demux — Workspace Planner: Development Plan (for Claude Code)

> Hand this file to Claude Code in the Demux repo (the Phase 0 monorepo).
> Goal: implement the **planner** end to end — prompt + email threads → validated **schema** — plus a re-runnable **benchmark**, first on 12 synthetic cases, then on Jihad's real Gmail threads.
> Privacy and PII handling are **out of scope** for this ticket. Do not build masking, redaction or hosting logic.

---

## 0. How to work

- Work on branch `feature/planner`. Small commits, one per step below.
- Follow `CLAUDE.md` conventions (routes → services → models, `uv`, `ruff`, `pytest`, `make` targets).
- **Stop and ask Jihad** at every point marked 🛑. Do not guess past a 🛑.
- Use sub-agents exactly as described in §5. Each one gets ONLY the inputs listed for it — it must not read the paths listed as forbidden.
- Never edit ground-truth files (`expected.yaml`) yourself. If you think a label is wrong, list it for Jihad.

---

## 1. Prerequisites — ask Jihad before writing code 🛑

Check each item; for anything missing, print this checklist with ✅/❌ and stop.

**Stage A (synthetic benchmark)**
1. The Phase 0 repo runs: `make setup && make db && make migrate && make test` pass.
2. A Hugging Face account with billing or credits enabled for **Inference Providers**.
3. A **fine-grained HF token** with the permission *"Make calls to Inference Providers"*, put in `backend/.env` as `HF_TOKEN=...` (never committed; confirm `.env` is git-ignored).

**Stage B (real Gmail — only needed at §8, ask again then)**
4. A Google Cloud project with the **Gmail API enabled**, an OAuth consent screen in *Testing* mode with Jihad's address as a test user, and an **OAuth client of type "Desktop app"**. The downloaded JSON goes to `backend/.secrets/gmail_credentials.json` (git-ignore `backend/.secrets/`).
5. In Gmail, each real test case's threads tagged with a label `demux-eval/<case-slug>` (this label **is** the mocked retrieval), plus the prompt for each case.

---

## 2. What the planner is (the contract)

**Input:** the user's `prompt` (string) + the threads that retrieval returned (mocked in this ticket).
**Output:** a `Schema` stored later in `workspaces.config`.
**Not in scope:** Gmail retrieval, extraction of values, reconciliation, UI generation, sync, API endpoint, persistence.

Vocabulary (use these words in code and comments): **workspace**, **prompt**, **schema**, **record type**, **record**, **field**, **thread**, **message**, stages **retrieval → sampling → planning → extraction → reconciliation → generation**.

### 2.1 Pydantic models — `backend/app/pipeline/planner/models.py`

```python
class FieldType(StrEnum): string, number, money, date, boolean, enum
class Origin(StrEnum):    explicit, inferred, observed
#   explicit = asked for in the prompt, or required by what the prompt asks to see
#              (e.g. a status/stage for a board)
#   inferred = planner's own guess from the prompt
#   observed = added because the sampled threads show it and it serves the prompt
class Support(StrEnum):   found, not_found      # does the information appear in the sample?
class Source(StrEnum):    thread, extracted
#   thread    = one record per thread (e.g. "my client emails as a board"); identity = thread id
#   extracted = records assembled from facts across messages (e.g. invoices)

class Field(BaseModel):
    name: str                       # snake_case, unique within its record type
    label: str                      # UI name, e.g. "Due date"
    description: str                # one sentence = the extraction instruction
    type: FieldType
    allowed_values: list[str] | None  # enum only: 2–6 snake_case values from the threads' wording
    origin: Origin
    support: Support
    justification: str | None       # required iff origin == observed: how it serves the prompt

class RecordType(BaseModel):
    name: str                       # snake_case singular, e.g. "invoice"
    label: str                      # UI name, e.g. "Invoices"
    description: str                # what one record is
    source: Source
    identity: str | None            # extracted only: one sentence, how to tell two mentions are the same record
    fields: list[Field]

class Schema(BaseModel):
    version: int = 1
    outcome: Literal["ok", "needs_clarification", "unsupported"]
    user_message: str | None        # required when outcome != ok, shown to the user
    scope: str | None               # natural-language: what the whole workspace covers
    record_types: list[RecordType]  # empty unless outcome == ok
    unresolved: list[str]           # internal diagnostics
```

Links between record types are **plain matching values**, not references: e.g. `project.client` is a string field holding the same value as `client.name`. The prompt must tell the model to do this when record types relate.

Thread input model (same file):

```python
class Message(BaseModel): message_id: str; sender: str; to: list[str]; date: datetime; subject: str; body: str; attachments: list[str] = []
class Thread(BaseModel):  thread_id: str; messages: list[Message]
```

### 2.2 Planning rules (go into the system prompt)

1. Decide the outcome first: `needs_clarification` when no concrete record type can be named from the prompt; `unsupported` when the information cannot come from email (e.g. profitability needing accounting data). Both carry a one-sentence `user_message` and no record types.
2. Model **as many record types as the prompt needs, and no more**.
3. Choose `source: thread` when one thread = one item the user wants to see; `extracted` when the item is assembled across messages/threads.
4. The prompt decides record types and explicit fields. Threads never remove an explicit field; if the information is absent, keep it with `support: not_found`.
5. Threads supply enum values (2–6, from their actual wording), sharper descriptions, and `observed` fields — only when they serve the prompt, each with a one-line `justification`.
6. Drop `inferred` fields the threads do not show.
7. Ignore threads unrelated to the prompt; they never change the record types.
8. When record types relate, the child carries a string field whose values match the parent's naming field.

### 2.3 Validator — `validate.py` (returns a list of human-readable errors; empty = valid)

| Rule | Check |
|---|---|
| Outcome | `ok` ⇒ ≥ 1 record type; otherwise `user_message` set and `record_types` empty |
| Caps (safety only) | ≤ 5 record types; each 1–12 fields |
| Names | snake_case; record type names unique; field names unique per record type after lowercasing and stripping `_` |
| Enums | `enum` ⇔ `allowed_values` with 2–6 unique values; other types have `None` |
| Identity | `extracted` ⇒ non-empty `identity`; `thread` ⇒ `identity` is `None` |
| Origin × support | `inferred` + `not_found` rejected; `observed` ⇒ `found` + non-empty `justification` |
| Text | no empty `label` / `description` |

### 2.4 Pipeline functions

- `app/pipeline/email_clean.py` — `clean_thread(thread) -> Thread`: drop quoted replies (`>` lines, "On … wrote:" blocks), signatures after `-- `, collapse whitespace. No PII work.
- `app/pipeline/sampling.py` — `sample_threads(threads, k=20) -> list[Thread]`, **deterministic**: sort by latest message date desc; prefer threads with ≥ 2 messages; at most 3 threads per sender domain; fill remaining slots in date order if constraints leave gaps.
- `app/pipeline/planner/prompts.py` — `SYSTEM_PROMPT`, `render_user_prompt(prompt, threads)`. Per thread render: id, date range, sender domains, message count, attachment names, subject, then cleaned bodies (oldest→newest, `→` between messages), **≤ 1,200 chars per thread**. Target total ≤ ~15k input tokens.
- `app/pipeline/planner/llm.py` — thin client (see §3).
- `app/pipeline/planner/plan.py` — `plan(prompt: str, threads: list[Thread]) -> PlanResult` where `PlanResult = {schema: Schema | None, valid_first_try: bool, attempts: int, errors: list[str], usage: {input_tokens, output_tokens}, latency_ms, raw_responses: list[str]}`. Clean → sample → call → parse → validate → on errors, **one retry** with the errors appended as a user message → if still invalid, `schema=None`.
- `app/pipeline/planner/cli.py` — `uv run python -m app.pipeline.planner.cli --prompt "..." --threads path/to/threads.json` prints the schema as JSON.

Settings (`app/core/config.py`): `HF_TOKEN`, `PLANNER_MODEL="Qwen/Qwen3.6-35B-A3B"`, `PLANNER_PROVIDER` (set after §4), `PLANNER_THINKING=false`, `PLANNER_TEMPERATURE`, `PLANNER_MAX_TOKENS=4000`. Add them to `.env.example`.

---

## 3. LLM access

- OpenAI SDK against the Hugging Face router: `base_url="https://router.huggingface.co/v1"`, `api_key=HF_TOKEN`, `model=f"{PLANNER_MODEL}:{PLANNER_PROVIDER}"` (provider pinned, never auto).
- Structured output: `response_format={"type":"json_schema","json_schema":{"name":"Schema","strict":true,"schema":<generated>}}`. Generate the JSON schema from the Pydantic models with `additionalProperties: false` and every property listed in `required` (nullable instead of optional) — strict mode on most providers needs that. Always parse with `Schema.model_validate_json` anyway.
- Qwen3.6 **thinks by default**. Non-thinking mode is `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`; the `/no_think` soft switch is not supported. Make thinking a setting, default off.
- If the chosen provider ignores `json_schema`: fall back to `{"type":"json_object"}` + the JSON schema pasted in the system prompt, and rely on the validator retry. Record which mode was used in each run.

---

## 4. Step 1 — Probe the model 🛑

Write `backend/scripts/probe_planner_model.py`:
1. List which providers serve `Qwen/Qwen3.6-35B-A3B` on the router (the router's `/v1/models` listing; if unclear, try candidate providers one by one with a 5-token request).
2. For each serving provider: one tiny structured-output call against a 3-field toy schema, with thinking off; record success, latency, token usage, whether `json_schema` was honoured.
3. Print a table and **stop**. Ask Jihad which provider to pin (prefer EU-based if one works; otherwise cheapest working one). Write his choice to `.env`.

---

## 5. Step 2 — Contract first, then three parallel tracks

### 5.1 Lead (you) writes the contract and commits it before spawning anyone
- `models.py` (§2.1) and function **stubs** with signatures and docstrings for `clean_thread`, `sample_threads`, `validate`, `plan`.
- `backend/eval/planner/FORMAT.md` — the case file formats (§6.1) and ground-truth format (§6.2).
- `backend/eval/planner/LABELING.md` — the labelling guide: §2.1 field meanings, §2.2 rules, and how to fill `expected.yaml`. Written so a stranger can label without any other context.

### 5.2 Spawn in parallel
| Agent | Gets ONLY | Produces | Must NOT read |
|---|---|---|---|
| **A — Case author** | §6.1 + §6.3 of this plan, `FORMAT.md` | 12 synthetic cases: `cases/<id>/request.yaml`, `cases/<id>/threads.json`; plus `_authoring/<id>/notes.md` (intent, planted traps, what a good schema should contain) | `app/`, `LABELING.md`, any `expected.yaml` |
| **C — Test writer** | §2.1, §2.3, §2.4 signatures, §6.2, §7 metric definitions, the stubs | `backend/tests/planner/` unit tests (validator: one test per rule, valid + invalid; sampler: determinism, ≤ 3 per domain, k cap, multi-message preference; cleaner: quotes/signatures; schema parsing round-trip) and `backend/eval/planner/scoring.py` + `tests/planner/test_scoring.py` (scorer tested on hand-made schema/expected pairs) | `app/pipeline/planner/prompts.py`, `plan.py`, `cases/`, `_authoring/` |
| **Lead** | everything | implementation of §2.4 + §3, the benchmark runner (§7) | `expected.yaml` contents while iterating on prompts (only read the scored diffs) |

### 5.3 After Agent A finishes: spawn **B — Ground-truth labeller** (fresh, no conversation context)
- Gets ONLY: `LABELING.md`, `FORMAT.md`, and for each case `request.yaml` + `threads.json`.
- Must NOT read: `_authoring/`, `app/`, `scoring.py`, this plan.
- Produces `cases/<id>/expected.yaml` for all 12 cases, labelling from the prompt and threads alone.

### 5.4 Cross-check 🛑
Compare each `_authoring/<id>/notes.md` with B's `expected.yaml`: outcome, record types, sources, required fields, `not_found` traps. Write `eval/planner/LABEL_REVIEW.md` listing every disagreement side by side. **Stop and ask Jihad to arbitrate.** Apply only his decisions to `expected.yaml` (commit message: `labels: arbitration by Jihad`).

---

## 6. Benchmark data

### 6.1 Case files (`backend/eval/planner/cases/<id>/`)

`request.yaml`
```yaml
id: invoices-unpaid
prompt: "Show me my unpaid invoices with amount and due date"
paraphrases:            # exactly 2, same intent, different wording — for the stability metric
  - "Which invoices haven't I paid yet? I need amounts and due dates"
  - "Track outstanding invoices: how much and when they're due"
domain: finance
holdout: false          # 3 of the 12 cases are true: excluded while iterating, run only at the end
```

`threads.json` — list of `Thread` (§2.1). **25–40 threads per case**, so sampling matters; 20–30% unrelated noise (newsletters, other clients, notifications). Realistic, messy: replies, forwards, short "ok thanks", status words in varied phrasing, some missing data.

### 6.2 Ground truth (`expected.yaml`)
```yaml
outcome: ok
record_types:
  - name: invoice
    synonyms: [bill, unpaid_invoice]
    source: extracted
    required_fields:
      - {name: amount,   synonyms: [total, invoice_amount], type: money, support: found}
      - {name: due_date, synonyms: [due, deadline],         type: date,  support: found}
      - {name: vendor,   synonyms: [supplier, from],        type: string, support: found}
    optional_fields:   [invoice_number, status, currency]   # allowed, not counted as over-generation
    forbidden_fields:  [sender_email_signature]             # counted as errors if present
forbidden_record_types: [vendor_contact]
notes: "one invoice has no number; one reminder has no amount"
```
For `needs_clarification` / `unsupported` cases: only `outcome` (+ optional `notes`).

### 6.3 The 12 synthetic cases — constraints for Agent A
- ≥ 4 cases with **2–3 record types** (e.g. clients + active projects; projects + pending approvals; vendors + invoices; properties + viewings).
- ≥ 4 cases with **`source: thread`** record types (e.g. "my client emails as a board by stage", "support requests that need a reply", "my inbox as a kanban by urgency").
- 1 `needs_clarification` ("What needs my attention?") and 1 `unsupported` ("Show my project profitability").
- Remaining: single extracted record types across finance, logistics, hiring, subscriptions/renewals, real estate.
- Every `ok` case plants ≥ 1 trap, spread across cases: an explicit field absent from all threads (→ `not_found`); messy status wording that must map to clean enum values; a key identifier missing in some messages; noise threads that look relevant.
- 3 cases marked `holdout: true`, chosen across categories.

### 6.4 Real cases (Stage B, §8) — `backend/eval/planner/real/<slug>/` (git-ignored)
Same three files; `threads.json` comes from Gmail, `expected.yaml` is drafted by a fresh labeller agent and **approved by Jihad**.

---

## 7. The benchmark

### 7.1 Command
```
make bench-planner                     # synthetic, non-holdout, 1 run per case
make bench-planner ARGS="--all"        # include holdout cases
make bench-planner ARGS="--real"       # add real cases if present
make bench-planner ARGS="--stability"  # also run the 2 paraphrases per case
make bench-planner ARGS="--case invoices-unpaid --thinking on --provider <p>"
make bench-planner ARGS="--rescore runs/<run_id>"   # re-score saved responses, no LLM calls
```
Implemented as `uv run python -m eval.planner ...` in `backend/`. Not run in CI (it costs money); `scoring.py` tests are.

### 7.2 Outputs — `backend/eval/planner/runs/<UTC-timestamp>_<model>_<provider>/`
- `responses/<case>[__p1|__p2].json` — prompt sent, raw responses, parsed schema, validator errors, usage, latency.
- `report.json` — config (model, provider, thinking, temperature, git SHA, prompt hash) + per-case scores + aggregates.
- `report.md` — metric table with ✅/❌ against thresholds, per-case diff (missing/extra record types and fields, wrong types/support/source), and deltas vs `runs/BASELINE` (a pointer file to the accepted run).
- Exit code 1 if any threshold fails.
- `runs/` is git-ignored except `BASELINE` and the baseline's `report.md`.

### 7.3 Scoring (deterministic, no LLM judge) — owned by Agent C
Matching: normalise names (lowercase, strip `_`, `-`, trailing `s`); a record type or field matches the label `name` or any `synonyms`. Record types are matched first; fields only within matched record types.

| Metric | Definition | Threshold |
|---|---|---|
| Outcome accuracy | outcome == label | ≥ 90% |
| Record type recall | labelled record types found / labelled | ≥ 90% |
| Record type precision | matched / produced (forbidden ones count as wrong) | ≥ 85% |
| Source accuracy | matched record types with the right `source` | ≥ 90% |
| Required-field recall | required fields found / required | ≥ 85% |
| Over-generation | fields not in required ∪ optional, per matched record type (forbidden count double) | ≤ 1.0 avg |
| Type accuracy | matched fields with the right `type` | ≥ 90% |
| Support accuracy | matched fields with the right `support` | ≥ 85% |
| Valid first try | validator passes without retry | ≥ 90% |
| Stability (`--stability`) | same outcome + same matched record types + ≥ 80% same required fields across prompt + 2 paraphrases | ≥ 80% of cases |
| Latency p50 / p95, cost per call | reported, not gated | — |

Cost per call is computed from usage × configurable prices in `eval/planner/prices.yaml`.

---

## 8. Step 3 — Iterate, then Stage B

### 8.1 Synthetic loop
1. `make test` green (Agent C's tests against your implementation). If a test looks wrong, do not change it silently — list it for Jihad.
2. `make bench-planner`. Iterate on `prompts.py` until thresholds pass on non-holdout cases.
   - Prompt changes must be **general rules**. Never put case-specific words, domains or values from the cases into the prompt.
   - Log each iteration in `eval/planner/PROMPT_LOG.md`: change, reason, key metric deltas.
   - Max 8 iterations. If still failing, stop 🛑 and report which metrics fail and why (and whether thinking mode helps: run once with `--thinking on`).
3. Final: `make bench-planner ARGS="--all --stability"`. Set `BASELINE` to this run. 🛑 Show Jihad `report.md`.

### 8.2 Real Gmail (Stage B) 🛑
Ask Jihad for prerequisites 4–5 (§1) and the list of `demux-eval/<slug>` labels + one prompt per label. Then:
1. `backend/scripts/fetch_gmail_fixture.py --label demux-eval/<slug> --out eval/planner/real/<slug>/threads.json` — `google-auth-oauthlib` desktop flow, scope `gmail.readonly`, token cached at `backend/.secrets/gmail_token.json`; fetch all threads with the label (`format=full`), decode text/plain (fallback: strip text/html), map to `Thread`. This is the mocked retrieval.
2. Write `request.yaml` from Jihad's prompts (no paraphrases needed unless he provides them).
3. Spawn a **fresh labeller agent** (same rules as B) to draft `expected.yaml`; 🛑 Jihad reviews and edits each one.
4. `make bench-planner ARGS="--real"` and report. Real-case thresholds are informational until Jihad decides.

---

## 9. Done when

1. `make lint` and `make test` pass (including Agent C's planner and scoring tests).
2. `uv run python -m app.pipeline.planner.cli --prompt ... --threads ...` prints a valid schema for any case.
3. `make bench-planner ARGS="--all --stability"` passes every threshold on the 12 synthetic cases with `Qwen/Qwen3.6-35B-A3B`; `BASELINE` points at that run.
4. The real Gmail cases run through the same benchmark and their report is shown to Jihad.
5. `README` section "Planner benchmark" explains how to run it, add a case, and update the baseline.

## 10. Out of scope
PII/privacy, provider hosting decisions, FastAPI endpoint, DB persistence of the schema, real retrieval, extraction, reconciliation, UI generation, sync/scheduler.
