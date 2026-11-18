"use client";

/**
 * Sandboxed iframe that runs a workspace's generated app.
 *
 * Security model (build spec §7.2):
 * - `sandbox="allow-scripts"` only: opaque origin, no same-origin access, no popups,
 *   no top navigation, no forms.
 * - srcdoc = fixed shell from the backend (CSP meta, base CSS, bridge) + agent HTML.
 * - Every message is checked with `event.source === iframe.contentWindow`.
 * - openSource accepts only Gmail-like hex ids; openLink only https URLs, after a
 *   confirm dialog owned by this (parent) page.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";

const THREAD_ID = /^[0-9a-f]{8,32}$/;

export function AppFrame({
  shellHead,
  html,
  appVersion,
  data,
  onError,
}: {
  shellHead: string;
  html: string;
  appVersion: number;
  data: unknown;
  onError: (message: string | null) => void;
}) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  // The frame reports ready per document; `readyFor` remembers which one.
  const [readyFor, setReadyFor] = useState<string | null>(null);
  const [pendingLink, setPendingLink] = useState<string | null>(null);

  const srcDoc = useMemo(
    () =>
      `<!doctype html><html><head>${shellHead}</head><body>${html}</body></html>`,
    [shellHead, html],
  );

  const postData = useCallback(() => {
    frameRef.current?.contentWindow?.postMessage(
      { type: "demux:data", data },
      "*",
    );
  }, [data]);

  const docKey = `${appVersion}:${srcDoc.length}`;
  const ready = readyFor === docKey;

  useEffect(() => {
    if (ready) postData();
  }, [ready, postData]);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (!frameRef.current || event.source !== frameRef.current.contentWindow)
        return;
      const msg = event.data;
      if (!msg || typeof msg.type !== "string") return;
      if (msg.type === "demux:ready") setReadyFor(docKey);
      else if (msg.type === "demux:rendered") onError(null);
      else if (msg.type === "demux:error")
        onError(String(msg.message ?? "Unknown error").slice(0, 500));
      else if (msg.type === "demux:openSource") {
        const id = String(msg.threadId ?? "");
        if (THREAD_ID.test(id)) {
          window.open(
            `https://mail.google.com/mail/u/0/#all/${id}`,
            "_blank",
            "noopener,noreferrer",
          );
        }
      } else if (msg.type === "demux:openLink") {
        const url = String(msg.url ?? "");
        try {
          if (new URL(url).protocol === "https:") setPendingLink(url);
        } catch {
          /* ignore invalid URLs */
        }
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [onError, docKey]);

  return (
    <div className="relative h-full w-full">
      <iframe
        key={appVersion}
        ref={frameRef}
        title="Workspace app"
        sandbox="allow-scripts"
        srcDoc={srcDoc}
        referrerPolicy="no-referrer"
        className="h-full w-full border-0 bg-surface"
      />
      {pendingLink && (
        <div className="absolute inset-0 grid animate-[dmx-fade_200ms_var(--ease-dmx)_both] place-items-center bg-[rgb(12_26_46/0.18)] p-4 backdrop-blur-[2px]">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="open-link-title"
            className="w-full max-w-md animate-dmx-rise rounded-lg bg-surface p-6 shadow-panel"
          >
            <p id="open-link-title" className="text-base font-semibold">
              Open this link?
            </p>
            <p className="mt-1 text-sm text-ink-2">
              It opens in a new tab, outside Demux.
            </p>
            <p className="mt-4 rounded-sm bg-surface-2 p-3 font-mono text-xs break-all text-ink-2">
              {pendingLink}
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button
                variant="quiet"
                onClick={() => setPendingLink(null)}
                autoFocus
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  window.open(pendingLink, "_blank", "noopener,noreferrer");
                  setPendingLink(null);
                }}
              >
                Open link
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
