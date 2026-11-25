"use client";

/**
 * Create (`/workspaces/new`, theme.md §8.1–8.2).
 *
 * Step "connect": while no Gmail is connected (or it needs a reconnect), one card with
 * "Connect with Google". Google sends the user back here (`?gmail=connected` or
 * `?error=…`). Step "prompt": "Hello, first name" (the name given at sign-up), "What do
 * you want to track?" and the prompt card. Build opens the new workspace in the same area.
 * Steps change inside a transition so they slide calmly (StepTransition).
 */
import { ArrowRight, Lock } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogoMark } from "@/components/brand/Logo";
import { StepTransition } from "@/components/motion/PageTransition";
import { Reveal, RevealText } from "@/components/motion/Reveal";
import { MAX_WORKSPACES, useShell } from "@/components/shell/AppShell";
import { ButtonLink } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { api, ApiError, handleAuthError } from "@/lib/api";
import { connectGmailUrl, useGmailReturn } from "@/lib/gmail";
import { PromptCard } from "./PromptCard";

export function CreateWorkspace() {
  const router = useRouter();
  const { me, workspaces, loadError, reload } = useShell();
  const { error: oauthError } = useGmailReturn();
  const [error, setError] = useState<string | null>(null);

  async function build(prompt: string): Promise<boolean> {
    setError(null);
    try {
      const ws = await api.createWorkspace(prompt);
      void reload(); // the drawer lists it right away
      router.push(`/workspaces/${ws.id}`);
      return true;
    } catch (e) {
      if (handleAuthError(e)) return false;
      if (e instanceof ApiError && e.code === "gmail_not_connected")
        await reload(); // back to the connect step
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
    : !me.gmail_connected || me.needs_reconnect
      ? "connect"
      : "prompt";
  const full = (workspaces?.length ?? 0) >= MAX_WORKSPACES;
  const problem = error ?? oauthError ?? loadError;

  return (
    <main className="flex min-h-dvh flex-col items-center px-4 pb-16">
      <StepTransition stepKey={step}>
        {step === "loading" ? (
          <div className="grid flex-1 place-items-center" aria-label="Loading">
            {/* Delayed so a fast load never flashes a spinner. */}
            <Reveal delay={250}>
              <Spinner size={28} />
            </Reveal>
          </div>
        ) : step === "connect" ? (
          <div className="flex w-full flex-1 items-center justify-center pt-20 pb-16">
            <ConnectCard reconnect={!!me?.needs_reconnect} error={problem} />
          </div>
        ) : (
          <div className="flex w-full flex-col items-center gap-6 pt-[clamp(88px,20vh,220px)]">
            <div className="flex flex-col items-center gap-3 text-center">
              <RevealText
                text={me?.first_name ? `Hello, ${me.first_name}` : "Hello"}
                className="text-[clamp(32px,3.4vw,46px)] leading-[1.06] font-medium tracking-[-0.035em]"
              />
              <Reveal
                as="p"
                index={2}
                className="text-[22px] leading-[1.3] font-medium tracking-[-0.02em] text-ink-on-sky"
              >
                What do you want to track?
              </Reveal>
            </div>
            <Reveal index={3} className="w-full max-w-[760px]">
              <PromptCard disabled={full} onBuild={build} />
            </Reveal>
            {full ? (
              <Reveal
                index={4}
                className="w-full max-w-[760px] rounded-[20px] bg-surface px-5 py-4 shadow-panel"
              >
                <div role="status">
                  <p className="text-[15px] font-semibold text-ink">
                    Workspace limit reached
                  </p>
                  <p className="mt-1 text-sm text-ink-2">
                    You can have {MAX_WORKSPACES} workspaces. Delete one to
                    create a new one.
                  </p>
                </div>
              </Reveal>
            ) : (
              <Reveal
                as="p"
                index={4}
                className="-mt-1 flex items-center gap-2 text-center text-[13px] text-ink-on-sky"
              >
                <Lock size={14} aria-hidden /> Read-only. Demux never sends or
                changes an email.
              </Reveal>
            )}
            {problem && (
              <p
                role="alert"
                className="w-full max-w-[760px] rounded-lg bg-danger-bg px-5 py-3 text-sm text-danger"
              >
                {problem}
              </p>
            )}
          </div>
        )}
      </StepTransition>
    </main>
  );
}

/** One idea: connect the Gmail Demux will read (it can differ from the login email). */
function ConnectCard({
  reconnect,
  error,
}: {
  reconnect: boolean;
  error: string | null;
}) {
  return (
    <Reveal
      as="section"
      className="flex w-full max-w-[520px] flex-col gap-6 rounded-2xl bg-surface px-7 pt-9 pb-7 shadow-float sm:px-9"
    >
      <LogoMark size={56} className="animate-dmx-breathe" />
      <div className="flex flex-col gap-3">
        <RevealText
          text={reconnect ? "Reconnect your Gmail" : "Connect your Gmail"}
          delay={120}
          className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em]"
        />
        <Reveal as="p" index={3} className="text-base text-ink-2">
          {reconnect
            ? "Google stopped letting Demux read your Gmail. Reconnect to keep your workspaces up to date."
            : "Demux reads the emails that match what you ask for and builds a workspace that keeps itself up to date. It can be a different account from the one you signed in with."}
        </Reveal>
      </div>
      {error && (
        <p
          role="alert"
          className="rounded-sm bg-danger-bg px-4 py-3 text-sm text-danger"
        >
          {error}
        </p>
      )}
      <Reveal index={4} className="flex flex-col items-center gap-4">
        <ButtonLink href={connectGmailUrl("new")} external className="w-full">
          Connect with Google{" "}
          <ArrowRight
            size={18}
            strokeWidth={2.2}
            aria-hidden
            className="dmx-nudge"
          />
        </ButtonLink>
        <p className="flex items-center gap-2 text-[13px] text-ink-3">
          <Lock size={14} aria-hidden /> Read-only. Demux never sends or changes
          an email.
        </p>
      </Reveal>
    </Reveal>
  );
}
