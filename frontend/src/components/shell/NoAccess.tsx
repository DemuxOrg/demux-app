"use client";

/**
 * Shown by the app shell instead of the sidebar and page when the signed-in user has no
 * access (theme.md §8, screen 5b): their subscription or trial ended, or their free
 * access was revoked or expired. The API answers 402 to every
 * workspace call meanwhile; the workspaces are kept and syncing is paused.
 *
 * "Subscribe" goes to the landing page's pricing card (a new checkout with a 14-day free
 * trial). "I've subscribed, check again" re-reads
 * Stripe right away; the shell's 15 s poll would also unlock the app once the webhook
 * has arrived.
 */
import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { Lockup, LogoMark } from "@/components/brand/Logo";
import { Reveal } from "@/components/motion/Reveal";
import { ButtonLink } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { LANDING_URL, api, handleAuthError, type Me } from "@/lib/api";
import { authClient } from "@/lib/auth-client";

const quiet =
  "inline-flex h-11 items-center gap-2 rounded-full px-1 font-medium transition-colors duration-150 ease-dmx focus-visible:ring-[3px] focus-visible:ring-violet/25 disabled:cursor-not-allowed disabled:opacity-40";

export function NoAccess({ me }: { me: Me }) {
  const [checking, setChecking] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function checkAgain() {
    setChecking(true);
    setNote(null);
    try {
      const fresh = await api.refreshAccess();
      if (fresh.access.status !== "none") {
        // Full load: pages kept mounted by Next would otherwise keep their 402 state.
        window.location.replace("/workspaces");
        return;
      }
      setNote(`Still no active subscription for ${fresh.email}.`);
    } catch (e) {
      if (!handleAuthError(e))
        setNote("We couldn't check right now. Try again in a minute.");
    } finally {
      setChecking(false);
    }
  }

  async function signOut() {
    setLeaving(true);
    await authClient.signOut().catch(() => undefined);
    window.location.replace("/login");
  }

  return (
    <div className="flex min-h-dvh flex-1 flex-col">
      <header className="flex items-center px-6 py-5 sm:px-8">
        <Reveal>
          <Lockup size={28} />
        </Reveal>
      </header>
      <main className="flex flex-1 items-center justify-center px-4 pt-4 pb-16">
        <Reveal className="w-full max-w-[480px]">
          <section className="flex flex-col gap-6 rounded-2xl bg-surface px-7 pt-8 pb-7 shadow-float sm:px-9 sm:pt-9">
            <div className="flex flex-col gap-4">
              <LogoMark size={46} />
              <div className="flex flex-col gap-2">
                <h1 className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em] text-balance text-ink">
                  Your Demux access has ended
                </h1>
                <p className="text-base text-pretty text-ink-2">
                  Subscribe to keep using Demux. Your workspaces are saved and
                  stop updating until then.
                </p>
                <p className="text-[13px] text-ink-3">
                  Signed in as{" "}
                  <span className="font-medium break-words text-ink-2">
                    {me.email}
                  </span>
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <ButtonLink
                href={me.access.subscribe_url || LANDING_URL}
                external
                className="w-full"
              >
                Subscribe
                <ArrowRight
                  size={18}
                  strokeWidth={2.2}
                  aria-hidden
                  className="dmx-nudge"
                />
              </ButtonLink>
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <button
                  type="button"
                  onClick={checkAgain}
                  disabled={checking}
                  className={`${quiet} text-violet hover:text-violet-ink`}
                >
                  {checking && <Spinner size={16} />}
                  I&apos;ve subscribed, check again
                </button>
                <button
                  type="button"
                  onClick={signOut}
                  disabled={leaving}
                  className={`${quiet} text-ink-2 hover:text-ink`}
                >
                  {leaving && <Spinner size={16} />}
                  Log out
                </button>
              </div>
              {note && (
                <p
                  role="status"
                  className="rounded-sm bg-violet-soft px-4 py-3 text-sm text-violet-ink"
                >
                  {note}
                </p>
              )}
            </div>
          </section>
        </Reveal>
      </main>
    </div>
  );
}
