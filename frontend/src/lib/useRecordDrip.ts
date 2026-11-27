"use client";

/**
 * Records arrive one by one (theme.md §7.10). The worker saves in batches; this hook
 * paces what the app shows: when new data arrives, it is diffed against the data on
 * screen by record key ("type/id") and `_updated_at`, and the creates, updates and
 * deletes are applied one every 300 ms (more per tick when more than 10 wait, so the
 * screen is never more than ~3 s behind, and the frame gets at most ~3 posts a second).
 *
 * - The first data shows as it is: a page opened mid-build never replays records.
 * - `paused` (a question moment is open) stops the ticks; they resume where they were.
 * - A hidden tab doesn't tick; when it shows again it jumps to the latest data.
 */
import { useEffect, useState } from "react";

export type Data = Record<string, unknown>;
type Op = { key: string; type: string; id: string; rec: unknown };

const TICK_MS = 300;
const MAX_BEHIND = 10; // ops per ~3 s before a tick applies several
const DELETED = Symbol("deleted");

function records(
  data: Data,
): Map<string, { type: string; id: string; rec: unknown }> {
  const out = new Map<string, { type: string; id: string; rec: unknown }>();
  for (const [type, recs] of Object.entries(data)) {
    if (type.startsWith("_") || !recs || typeof recs !== "object") continue;
    for (const [id, rec] of Object.entries(recs as Record<string, unknown>))
      out.set(`${type}/${id}`, { type, id, rec });
  }
  return out;
}

function stamp(rec: unknown): string {
  const at = (rec as { _updated_at?: unknown } | null)?._updated_at;
  return typeof at === "string" ? at : JSON.stringify(rec);
}

/** What changes `from` into `to`: creates and updates in `to`'s order, then deletes. */
export function diff(from: Data, to: Data): Op[] {
  const before = records(from);
  const ops: Op[] = [];
  for (const [key, r] of records(to)) {
    const old = before.get(key);
    if (!old || stamp(old.rec) !== stamp(r.rec)) ops.push({ key, ...r });
    before.delete(key);
  }
  for (const [key, r] of before) ops.push({ key, ...r, rec: DELETED });
  return ops;
}

function apply(shown: Data, target: Data, ops: Op[]): Data {
  const next: Data = {};
  // System keys ("_…") follow the target directly.
  for (const [k, v] of Object.entries(target))
    if (k.startsWith("_")) next[k] = v;
  for (const [k, v] of Object.entries(shown))
    if (!k.startsWith("_")) next[k] = { ...(v as object) };
  for (const op of ops) {
    const recs = (next[op.type] ??= {}) as Record<string, unknown>;
    if (op.rec === DELETED) delete recs[op.id];
    else recs[op.id] = op.rec;
  }
  return next;
}

type State = {
  target: Data | null;
  shown: Data | null;
  queue: Op[];
  changed: string[];
};

export function useRecordDrip(target: Data | null, paused: boolean) {
  const [s, setS] = useState<State>({
    target,
    shown: target,
    queue: [],
    changed: [],
  });

  // New data from the server: start (or restart) the queue from what is on screen.
  if (target !== s.target) {
    const hidden = typeof document !== "undefined" && document.hidden;
    setS(
      !target || !s.shown || hidden
        ? { target, shown: target, queue: [], changed: [] }
        : { ...s, target, queue: diff(s.shown, target) },
    );
  }

  const waiting = s.queue.length > 0;
  useEffect(() => {
    if (!waiting || paused) return;
    const timer = setInterval(() => {
      if (document.hidden) return;
      setS((cur) => {
        if (!cur.queue.length || !cur.shown || !cur.target) return cur;
        const n = Math.max(1, Math.ceil(cur.queue.length / MAX_BEHIND));
        const ops = cur.queue.slice(0, n);
        return {
          ...cur,
          shown: apply(cur.shown, cur.target, ops),
          queue: cur.queue.slice(n),
          changed: ops.filter((o) => o.rec !== DELETED).map((o) => o.key),
        };
      });
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [waiting, paused]);

  // Back from a hidden tab: jump to the latest data, no animation.
  useEffect(() => {
    const onShow = () => {
      if (document.hidden) return;
      setS((cur) =>
        cur.queue.length
          ? { ...cur, shown: cur.target, queue: [], changed: [] }
          : cur,
      );
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, []);

  return { data: s.shown, changed: s.changed, behind: s.queue.length };
}
