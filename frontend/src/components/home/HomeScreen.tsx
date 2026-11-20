"use client";

/**
 * Home (`/workspaces`).
 *
 * Step 1, "connect": shown whenever the user has no workspace (and always while no
 * Gmail is connected). Step 2, "prompt": the question, the prompt card and the two
 * workspace slots. Coming back from Google (`?gmail=connected`) goes straight to step 2.
 * Steps change inside a transition so they slide calmly (StepTransition).
 */
import { useRouter } from "next/navigation";
import { startTransition, useCallback, useEffect, useState } from "react";
import { AccountMenu } from "@/components/AccountMenu";
import { Lockup } from "@/components/brand/Logo";
import { StepTransition } from "@/components/motion/PageTransition";
import { Spinner } from "@/components/ui/Spinner";
import { Lock } from "lucide-react";
import {
  api,
  ApiError,
  CONNECT_GMAIL_URL,
  handleAuthError,
  type Me,
  type WorkspaceSummary,
} from "@/lib/api";
import { ButtonLink } from "@/components/ui/Button";
import { ConnectGmail } from "./ConnectGmail";
import { PromptCard } from "./PromptCard";
import { MAX_WORKSPACES, WorkspaceSlots } from "./WorkspaceSlots";

const OAUTH_ERRORS: Record<string, string> = {
  google_denied:
    "Gmail wasn't connected: the Google screen was closed or cancelled.",
  bad_state: "That link expired. Connect Gmail again.",
  google_failed: "Google didn't let us connect. Try again.",
  gmail_scope_missing:
    "Demux needs read access to Gmail. Tick the Gmail box on Google's screen and try again.",
};

export function HomeScreen() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[] | null>(null);
  const [continued, setContinued] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Read (and clear) the result of the Google round trip.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("error");
    const connected = params.get("gmail") === "connected";
    if (code || connected) {
      startTransition(() => {
        if (code)
          setOauthError(
            OAUTH_ERRORS[code] ?? "Gmail wasn't connected. Try again.",
          );
        if (connected) setContinued(true);
      });
      window.history.replaceState(null, "", "/workspaces");
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const [m, ws] = await Promise.all([api.me(), api.listWorkspaces()]);
      startTransition(() => {
        setMe(m);
        setWorkspaces(ws);
      });
    } catch (e) {
      if (!handleAuthError(e))
        setError(
          e instanceof Error ? e.message : "Couldn't load your workspaces.",
        );
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    const t = setInterval(load, 15000);
    return () => {
      clearTimeout(first);
      clearInterval(t);
    };
  }, [load]);

  async function build(prompt: string): Promise<boolean> {
    setError(null);
    try {
      const ws = await api.createWorkspace(prompt);
      router.push(`/workspaces/${ws.id}`);
      return true;
    } catch (e) {
      if (handleAuthError(e)) return false;
      if (e instanceof ApiError && e.code === "gmail_not_connected") {
        startTransition(() => setContinued(false));
        await load();
      }
      setError(
        e instanceof ApiError
          ? e.message
          : "Couldn't start the build. Try again.",
      );
      return false;
    }
  }

  const ready = me !== null && workspaces !== null;
  const step = !ready
    ? "loading"
    : !me.gmail_connected || (workspaces.length === 0 && !continued)
      ? "connect"
      : "prompt";
  const full = (workspaces?.length ?? 0) >= MAX_WORKSPACES;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between px-6 py-[18px] sm:px-8">
        <Lockup size={28} />
        <AccountMenu me={me} />
      </header>

      {me?.needs_reconnect && (
        <div className="mx-auto mb-2 w-full max-w-[760px] px-4">
          <div className="glass flex flex-wrap items-center gap-3 rounded-lg px-5 py-3 shadow-glass">
            <p className="min-w-0 flex-1 text-sm">
              Gmail disconnected. Reconnect to keep your workspaces updated.
            </p>
            <ButtonLink href={CONNECT_GMAIL_URL} external size="sm">
              Reconnect Gmail
            </ButtonLink>
          </div>
        </div>
      )}

      <main className="flex flex-1 flex-col items-center px-4 pb-16">
        <StepTransition stepKey={step}>
          {step === "loading" ? (
            <div
              className="grid flex-1 place-items-center pb-24"
              aria-label="Loading"
            >
              <Spinner size={28} />
            </div>
          ) : step === "connect" ? (
            <div className="flex w-full flex-1 items-center justify-center pt-6 pb-16">
              <ConnectGmail
                me={me!}
                error={oauthError ?? error}
                onContinue={() => startTransition(() => setContinued(true))}
              />
            </div>
          ) : (
            <div className="flex w-full flex-col items-center gap-6 pt-[clamp(24px,8vh,96px)]">
              <h1 className="max-w-[760px] text-center text-[clamp(32px,3.4vw,46px)] leading-[1.06] font-medium tracking-[-0.035em]">
                What do you want to see from your inbox?
              </h1>
              <PromptCard
                disabled={full || !!me?.needs_reconnect}
                onBuild={build}
              />
              <p className="-mt-1 flex items-center gap-2 text-[13px] text-ink-on-sky">
                <Lock size={14} aria-hidden /> Read-only. Demux never sends or
                changes an email.
              </p>
              {(error || oauthError) && (
                <p
                  role="alert"
                  className="w-full max-w-[760px] rounded-lg bg-danger-bg px-5 py-3 text-sm text-danger"
                >
                  {error ?? oauthError}
                </p>
              )}
              <div className="mt-[clamp(16px,6vh,64px)] w-full max-w-[760px]">
                <WorkspaceSlots workspaces={workspaces!} />
              </div>
            </div>
          )}
        </StepTransition>
      </main>
    </div>
  );
}
