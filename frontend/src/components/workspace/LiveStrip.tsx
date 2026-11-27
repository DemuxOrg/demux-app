"use client";

/**
 * The live build's strip (theme.md §7.10): one line of real facts, the brand-gradient bar
 * filled to threads read ÷ threads found, and Cancel, which asks inline first.
 */
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

export function LiveStrip({
  line,
  share,
  note,
  onCancel,
}: {
  line: string;
  /** Threads read ÷ threads found, 0–1. */
  share: number;
  /** The second line ("That's everything we need from you…" or a timeout notice). */
  note: string | null;
  onCancel: () => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  return (
    <div className="mx-3 mb-3 sm:mx-4">
      <div className="glass rounded-[20px] py-2 pr-2 pl-[18px] shadow-glass">
        <div className="flex min-h-9 items-center gap-3">
          <p
            className="min-w-0 flex-1 truncate text-sm font-medium text-ink tabular"
            aria-live="polite"
          >
            {line}
          </p>
          {!confirming && (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              className="h-11 shrink-0 rounded-full px-3 text-[13px] font-medium text-ink-3 transition-colors hover:text-danger"
            >
              Cancel
            </button>
          )}
        </div>
        <span
          aria-hidden
          className="mr-2.5 mb-1 block h-1 overflow-hidden rounded-full bg-track"
        >
          <span
            className="block h-full animate-dmx-flow rounded-full bg-brand-flow transition-[width] duration-500 ease-dmx"
            style={{ width: `${Math.max(4, Math.round(share * 100))}%` }}
          />
        </span>
        {note && !confirming && (
          <p className="mt-1.5 mb-0.5 text-[13px] text-ink-3">{note}</p>
        )}
        {confirming && (
          <CancelConfirm
            onKeep={() => setConfirming(false)}
            onStop={onCancel}
          />
        )}
      </div>
    </div>
  );
}

/** "Stop this build?", inline (theme.md §7.10). */
function CancelConfirm({
  onKeep,
  onStop,
}: {
  onKeep: () => void;
  onStop: () => Promise<void>;
}) {
  const [stopping, setStopping] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onKeep();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onKeep]);

  async function stop() {
    setStopping(true);
    setFailed(false);
    try {
      await onStop();
    } catch {
      setFailed(true);
      setStopping(false);
    }
  }

  return (
    <div
      role="alertdialog"
      aria-labelledby="cancel-build"
      className="mt-2 mb-1 mr-2.5 flex animate-dmx-rise flex-wrap items-center gap-x-3 gap-y-2 rounded-sm bg-danger-bg px-4 py-2.5"
    >
      <p
        id="cancel-build"
        className="min-w-0 flex-1 basis-60 text-sm text-danger"
      >
        {failed
          ? "Couldn't stop the build. Try again."
          : "Stop this build? The workspace is removed and your prompt goes back in the box."}
      </p>
      <div className="ml-auto flex items-center gap-1">
        <Button variant="quiet" size="sm" onClick={onKeep} autoFocus>
          Keep building
        </Button>
        <button
          type="button"
          onClick={stop}
          disabled={stopping}
          className="inline-flex h-11 items-center gap-2 rounded-full px-3 text-sm font-medium text-danger hover:underline disabled:opacity-70"
        >
          {stopping && <Spinner size={16} />}
          Stop build
        </button>
      </div>
    </div>
  );
}
