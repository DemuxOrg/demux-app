"use client";

/**
 * Connecting Gmail from the browser. The backend owns the Google flow: the page sends the
 * user to `connectGmailUrl(next)`, Google sends them back to that page with
 * `?gmail=connected` or `?error=<code>`, which `useGmailReturn()` reads once and clears.
 */
import { startTransition, useEffect, useState } from "react";
import { CONNECT_GMAIL_URL } from "./api";

/** Pages Google can return to (the backend keeps the same fixed list). */
export type GmailReturnPage = "new" | "profile";

export function connectGmailUrl(next: GmailReturnPage): string {
  return `${CONNECT_GMAIL_URL}?next=${next}`;
}

const OAUTH_ERRORS: Record<string, string> = {
  google_denied:
    "Gmail wasn't connected: the Google screen was closed or cancelled.",
  bad_state: "That link expired. Connect Gmail again.",
  google_failed: "Google didn't let us connect. Try again.",
  gmail_scope_missing:
    "Demux needs read access to Gmail. Tick the Gmail box on Google's screen and try again.",
};

export function useGmailReturn(): { connected: boolean; error: string | null } {
  const [result, setResult] = useState<{
    connected: boolean;
    error: string | null;
  }>({ connected: false, error: null });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("error");
    const connected = params.get("gmail") === "connected";
    if (code || connected)
      startTransition(() =>
        setResult({
          connected,
          error: code
            ? (OAUTH_ERRORS[code] ?? "Gmail wasn't connected. Try again.")
            : null,
        }),
      );
    if (window.location.search)
      window.history.replaceState(null, "", window.location.pathname);
  }, []);

  return result;
}
