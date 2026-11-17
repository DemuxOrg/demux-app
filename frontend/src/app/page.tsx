"use client";

/**
 * Landing page (`/`). Signed out: product line + "Connect Gmail". Signed in:
 * redirect to /workspaces. Shows sign-in errors passed back by the OAuth callback.
 */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, LOGIN_URL } from "@/lib/api";

const ERRORS: Record<string, string> = {
  google_denied: "Google sign-in was cancelled.",
  bad_state: "The sign-in link expired. Please try again.",
  google_failed: "Google sign-in failed. Please try again.",
  gmail_scope_missing:
    "Demux needs read access to Gmail. Please allow it on the Google screen.",
};

export default function Home() {
  const router = useRouter();
  const [state, setState] = useState<"checking" | "out" | "down">("checking");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("error");
    api
      .me()
      .then(() => router.replace("/workspaces"))
      .catch(() => {
        if (code) setError(ERRORS[code] ?? "Sign-in failed.");
        return api
          .health()
          .then(() => setState("out"))
          .catch(() => setState("down"));
      });
  }, [router]);

  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <h1 className="mb-3 text-3xl font-semibold">Your inbox, as a workspace.</h1>
      <p className="mb-8 text-gray-600">
        Describe what you want to see — unpaid invoices, job applications, orders
        on the way — and Demux builds a live view from your Gmail that keeps
        itself up to date.
      </p>
      {error && (
        <p className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {state === "down" ? (
        <p className="text-red-600">The backend is not reachable on {LOGIN_URL.split("/api")[0]}.</p>
      ) : (
        <a
          href={LOGIN_URL}
          className={`inline-block rounded bg-gray-900 px-5 py-2.5 text-white ${state === "checking" ? "pointer-events-none opacity-50" : ""}`}
        >
          Connect Gmail
        </a>
      )}
      <p className="mt-4 text-xs text-gray-500">
        Read-only access. Demux never sends, deletes or changes your email.
      </p>
    </div>
  );
}
