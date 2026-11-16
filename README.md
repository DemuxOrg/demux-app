# Demux

Turns a user's Gmail into structured, refreshable workspaces. You sign in with Google, type what you want to see ("show my unpaid invoices and who I owe"), and an agent builds a live view from your mail. The view keeps itself up to date, you can change it by chat, and Undo reverts any change.

Stack: FastAPI + SQLAlchemy (async) + Postgres 17 · Next.js (App Router) + Tailwind · an OpenAI-compatible LLM with tool calling · Playwright (app checks) · `uv`, `pnpm`, `make`.

## Run it

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 22+, [pnpm](https://pnpm.io/), make.

### 1. Google Cloud (one-off, ~10 minutes)
1. Go to [console.cloud.google.com](https://console.cloud.google.com/) and create a project. Then **APIs & Services → Library → Gmail API → Enable**.
2. Set up **OAuth consent screen** (Google Auth Platform → Branding / Audience):
   - User type: **External**. Publishing status: **Testing**.
   - Add your Gmail address under **Test users**.
   - Data access: add the scope `https://www.googleapis.com/auth/gmail.readonly`.
3. Create the client: **Clients → Create client → Web application**.
   - Authorized redirect URI: `http://localhost:8000/api/v1/auth/google/callback`
   - Put the client ID and secret into the repo-root `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

While the app is in *Testing*, Google expires the Gmail grant after about 7 days. Demux then shows a **Reconnect Gmail** banner and pauses syncing until you sign in again.

### 2. LLM
Set `LLM_BASE_URL` and `LLM_API_KEY` in `.env`. The default is the Hugging Face router, and `LLM_API_KEY` falls back to `HF_TOKEN`. Pick the models with `BUILD_MODEL` and `SYNC_MODEL`. Check that a model can drive the agent with:

```bash
cd backend && PYTHONPATH=. uv run python scripts/probe_agent_model.py "Qwen/Qwen3.8-27B:nebius" "Qwen/Qwen3.8-27B:nscale"
```

Prices for cost tracking and budgets live in `backend/app/agent/prices.yaml`.

**Speed.** The defaults aim for a build in about a minute:
- a fast model (`Qwen/Qwen3.8-27B` on Nebius, with nScale as `LLM_FALLBACK_MODEL` when the main one keeps failing) and `LLM_REASONING_EFFORT=none` (the model answers without a thinking pass; `low` is better but several times slower);
- a design phase limited to 8 searches and 10 sampled threads;
- email batches read in parallel (`PROCESS_CONCURRENCY`), with the app written at the same time;
- the newest `BUILD_MAX_THREADS=80` matching threads.

A stronger, slower model (for example `zai-org/GLM-5.3:deepinfra`) gives better records but takes minutes.

### 3. Start
```bash
make setup     # deps, Chromium for app checks, .env, SECRET_KEY + TOKEN_ENCRYPTION_KEY
make db        # Postgres
make migrate
make backend   # terminal 1 — API on :8000
make worker    # terminal 2 — runs builds, edits and the 10-minute syncs
make frontend  # terminal 3 — http://localhost:3000
```

Open http://localhost:3000 → **Connect Gmail** → type a prompt → **Build**.

**Without Gmail:** with `ENV=dev`, set `DEV_FAKE_MAILBOX=eval/agent/scenarios/04-client-board-stages/mailbox.json` in `.env`. The path is relative to `backend/`. The worker then reads that JSON instead of Gmail. You still sign in with Google.

## How the agent works

One agent with a handful of tools edits a workspace made of three things:
- an **app**: one self-contained HTML document;
- its **data**: JSON records grouped by type;
- a **guide**: the agent's own notes on the record types, the id rules and what to ignore.

Gmail **queries** chosen at build time define which mail belongs to the workspace.

- **Build:**
  1. *Design.* The agent explores your mail with `search_mail` and `read_thread`, then writes the guide and the queries.
  2. *Backfill.* Matching threads are read in parallel batches, and the agent saves records. Stable record ids make saves to the same record merge, and the store lets older emails only fill empty fields, so newer emails always win.
  3. *App.* At the same time, the agent writes the app from the guide. Each version is checked statically and then rendered in headless Chromium with the network blocked. A failed check goes back to the agent to fix.
- **Sync** runs every `SYNC_INTERVAL_MIN`. It only looks at messages not processed yet; if there are none, it makes no LLM call. The app is never touched.
- **Edit** happens by chat and makes the smallest change. It can rewrite the app, change the guide, fix records, change the queries, or request a re-read of all mail.

**Data integrity:**
- Every saved record must cite messages the agent actually read in that run.
- Every run snapshots the workspace first, so **Undo** restores the previous state.
- Every record change is logged, and the **Activity** tab shows it with an "open email" link.

**Security and privacy:**
- The generated app runs in a `sandbox="allow-scripts"` iframe with a strict CSP and no network. It talks to the page only through `postMessage`.
- Google tokens stay in the backend, Fernet-encrypted.
- Logs contain ids, counts, tool names and costs, never email content.

**Inspecting a workspace:** ⋯ → **Details** shows the prompt, the guide, the queries, and every run with its cost and tokens.

**CLI without the web app:**
```bash
cd backend
uv run python -m app.agent.cli build --prompt "..." --mailbox fake:tests/fixtures/mailbox_small.json --out .runs/cli/demo --now 2026-10-16T00:00:00Z
uv run python -m app.agent.cli sync  --mailbox fake:tests/fixtures/mailbox_small.json --out .runs/cli/demo --now 2026-10-22T00:00:00Z
uv run python -m app.agent.cli edit  --mailbox fake:... --out .runs/cli/demo --message "sort by date"
```
Use `--mailbox gmail:<you@gmail.com>` to run against a signed-in user's Gmail. Open `.runs/cli/demo/preview.html` in a browser to see the app.

## Eval

These runs cost money and are not part of CI.

| Command | What it does |
|---|---|
| `make eval-agent` | Runs the 8 synthetic scenarios in `backend/eval/agent/scenarios/` and writes `backend/eval/agent/runs/<ts>/report.md` + `report.json` |
| `make eval-agent ARGS="--repeats 3"` | Repeats the full run 3 times; gate decisions on the mean |
| `make eval-agent ARGS="--scenario 01 07"` | Runs a subset of scenarios |
| `make eval-agent ARGS="--replay --workspace <id> --days 14"` | Builds a copy of a real workspace 14 days back, syncs it day by day, and compares it with a fresh build |

Reports with email-derived values are git-ignored. To score a real-world trial, use `docs/TRIAL.md`.

## Everyday commands

| Command | What it does |
|---|---|
| `make lint` | ruff + eslint + `tsc --noEmit` |
| `make test` | backend tests, including app checks and the sandbox security test (needs `make db`) |
| `make migration m="msg"` | autogenerate an Alembic migration |
| `make gen-api` | regenerate frontend API types (backend must be running) |

## Learn the repo
- [`docs/REPO_GUIDE.md`](docs/REPO_GUIDE.md): Phase 0 tour.
- [`docs/project_instructions/Demux_Simple_Agent_MVP_Build_Spec.md`](docs/project_instructions/Demux_Simple_Agent_MVP_Build_Spec.md): this build.
- [`CLAUDE.md`](CLAUDE.md): conventions.
