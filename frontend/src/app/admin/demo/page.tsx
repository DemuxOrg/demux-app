"use client";

/**
 * Demo inbox (theme.md §8, screen 6): describe a prospect's persona, and the worker
 * writes synthetic threads into the test Gmail with the LLM. Then connect that inbox to
 * Demux and build workspaces on it.
 */
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import {
  Card,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pill,
  dateTime,
  num,
  statusTone,
  useAdminData,
  usd,
} from "@/components/admin/ui";
import { ApiError, adminApi, handleAuthError } from "@/lib/api";

const EXAMPLES = [
  "I'm a UGC creator. Threads with brands about paid deals: briefs, rates, contracts, deliverables, invoices and late payments.",
  "I run a small wedding photography studio. Inquiries, quotes, booked dates, deposits and album deliveries.",
  "I'm a freelance recruiter. Candidates, client roles, interview scheduling, offers and placement fees.",
];
const COUNTS = [5, 10, 15, 20, 30, 40];

function message(e: unknown): string {
  return e instanceof ApiError || e instanceof Error
    ? e.message
    : "Something went wrong.";
}

export default function AdminDemoPage() {
  const { data, error, reload } = useAdminData("demo", adminApi.demo);
  const [prompt, setPrompt] = useState("");
  const [count, setCount] = useState(15);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [cleaning, setCleaning] = useState<"idle" | "confirm" | "busy">("idle");
  const [cleanNote, setCleanNote] = useState<string | null>(null);

  const active = data?.seeds.some(
    (s) => s.status === "queued" || s.status === "running",
  );

  // Poll while the worker is writing threads.
  useEffect(() => {
    if (!active) return;
    const t = setInterval(reload, 3000);
    return () => clearInterval(t);
  }, [active, reload]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await adminApi.createSeed(prompt.trim(), count);
      reload();
    } catch (err) {
      if (!handleAuthError(err)) setFormError(message(err));
    } finally {
      setBusy(false);
    }
  }

  async function cleanup() {
    setCleaning("busy");
    setCleanNote(null);
    try {
      const { removed } = await adminApi.cleanupDemo();
      setCleanNote(
        removed
          ? `Moved ${num(removed)} demo messages to Trash.`
          : "No demo messages to remove.",
      );
    } catch (err) {
      if (!handleAuthError(err)) setCleanNote(message(err));
    } finally {
      setCleaning("idle");
    }
  }

  if (error) return <ErrorNote message={error} />;
  if (!data) return <Loading />;

  return (
    <>
      <PageHeader
        title="Demo inbox"
        note={
          data.inbox_email
            ? `Writes synthetic threads into ${data.inbox_email}. Then connect it to Demux and build workspaces on it.`
            : "Writes synthetic threads into a test Gmail for prospect demos."
        }
      />
      {!data.configured && (
        <ErrorNote message="The demo inbox is not configured. Set TEST_GMAIL and TEST_GMAIL_PASSWORD (a Google app password) in .env, then restart the backend and worker." />
      )}
      <Card
        title="Who is the inbox owner, and what threads do they get?"
        note={`Written by ${data.model}. Threads are dated over the last 45 days; nothing is sent.`}
      >
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label htmlFor="persona" className="sr-only">
            Persona and threads
          </label>
          <textarea
            id="persona"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            maxLength={2000}
            placeholder="I'm a UGC creator. Threads with brands about paid deals…"
            className="w-full resize-y rounded-sm border border-line bg-surface px-4 py-3 text-base text-ink caret-violet placeholder:text-ink-3 focus:border-violet-line focus:shadow-[0_0_0_3px_rgb(106_61_240/0.22)] focus:outline-none"
          />
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => setPrompt(ex)}
                className="h-9 max-w-full truncate rounded-full border border-chip-line bg-surface-3 px-3.5 text-sm font-medium text-ink-2 hover:border-violet-line hover:bg-violet-soft hover:text-violet-ink"
              >
                {ex.split(".")[0]}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-[13px] font-medium text-ink-2">
              Threads
              <select
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="h-10 rounded-full border border-line bg-surface px-3 text-sm text-ink focus:border-violet-line focus:outline-none"
              >
                {COUNTS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <Button
              type="submit"
              loading={busy}
              disabled={
                !data.configured || prompt.trim().length < 10 || !!active
              }
            >
              Write threads
            </Button>
          </div>
          {active && (
            <p className="text-[13px] text-ink-3">
              Writing threads. This takes about a minute.
            </p>
          )}
          {formError && <p className="text-sm text-danger">{formError}</p>}
        </form>
      </Card>

      <Card
        title="Requests"
        right={
          cleaning === "confirm" ? (
            <span className="flex flex-wrap items-center gap-2 text-[13px] text-ink-2">
              Move every demo thread to Trash?
              <Button variant="quiet" onClick={() => setCleaning("idle")}>
                Cancel
              </Button>
              <button
                type="button"
                onClick={cleanup}
                className="h-11 rounded-full px-3 text-sm font-medium text-danger hover:bg-danger-bg"
              >
                Move to Trash
              </button>
            </span>
          ) : (
            <Button
              variant="quiet"
              loading={cleaning === "busy"}
              disabled={!data.configured}
              onClick={() => setCleaning("confirm")}
            >
              Move demo threads to Trash
            </Button>
          )
        }
      >
        {cleanNote && (
          <p className="mb-3 text-[13px] text-ink-2">{cleanNote}</p>
        )}
        {data.seeds.length === 0 ? (
          <Empty>Nothing written yet.</Empty>
        ) : (
          <ul className="flex flex-col">
            {data.seeds.map((s) => (
              <li
                key={s.id}
                className="flex flex-col gap-1 border-t border-line-soft py-3 first:border-t-0"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    <Pill tone={statusTone(s.status)}>{s.status}</Pill>
                    <span className="tabular text-[13px] text-ink-2">
                      {s.status === "done"
                        ? `${num(s.threads_created)} threads · ${num(s.messages_created)} messages`
                        : `${num(s.thread_count)} threads asked`}
                      {" · "}
                      {usd(s.cost_usd)}
                    </span>
                  </span>
                  <span className="text-[13px] text-ink-3">
                    {dateTime(s.created_at)}
                  </span>
                </div>
                <p className="line-clamp-2 text-sm text-pretty text-ink">
                  {s.prompt}
                </p>
                {s.error && (
                  <p className="text-[13px] text-danger">{s.error}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
