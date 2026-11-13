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
        className="h-full w-full border-0 bg-white"
      />
      {pendingLink && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/30">
          <div className="max-w-md rounded-lg bg-white p-5 shadow-lg">
            <p className="mb-2 font-medium">Open this link?</p>
            <p className="mb-4 rounded bg-gray-100 p-2 font-mono text-xs break-all">
              {pendingLink}
            </p>
            <div className="flex justify-end gap-2">
              <button
                className="rounded border px-3 py-1.5 text-sm"
                onClick={() => setPendingLink(null)}
              >
                Cancel
              </button>
              <button
                className="rounded bg-gray-900 px-3 py-1.5 text-sm text-white"
                onClick={() => {
                  window.open(pendingLink, "_blank", "noopener,noreferrer");
                  setPendingLink(null);
                }}
              >
                Open
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
