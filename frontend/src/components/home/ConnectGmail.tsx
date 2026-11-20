/**
 * First screen whenever the user has no workspace yet: connect the Gmail that Demux will
 * read. If one is already connected, it shows which and lets the user continue (or pick
 * another account). The Gmail can differ from the login email.
 */
import { ArrowRight, Check, Lock } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { Reveal, RevealText } from "@/components/motion/Reveal";
import { Button, ButtonLink } from "@/components/ui/Button";
import { CONNECT_GMAIL_URL, type Me } from "@/lib/api";

export function ConnectGmail({
  me,
  error,
  onContinue,
}: {
  me: Me;
  error: string | null;
  onContinue: () => void;
}) {
  const connected = me.gmail_connected;
  return (
    <section className="w-full max-w-[620px] rounded-2xl bg-surface px-7 pt-9 pb-7 shadow-float sm:px-9">
      <div className="flex flex-col gap-6">
        <LogoMark size={56} className="animate-dmx-breathe" />
        <div className="flex flex-col gap-3">
          <RevealText
            key={connected ? "connected" : "connect"}
            text={connected ? "Your Gmail is connected" : "Connect your Gmail"}
            delay={120}
            className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em]"
          />
          <Reveal as="p" index={3} className="text-base text-ink-2">
            {connected
              ? "Next, describe what you want to keep track of. Demux reads the matching emails and builds a workspace that stays up to date."
              : "Demux reads the emails that match what you ask for, then builds a workspace that keeps itself up to date. It can be a different account from the one you signed in with."}
          </Reveal>
        </div>

        {connected ? (
          <div className="flex items-center gap-3 rounded-lg border border-line px-4 py-3">
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-violet-soft text-violet">
              <Check size={16} strokeWidth={2.4} aria-hidden />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[13px] text-ink-3">Reading from</span>
              <span className="block truncate text-[15px] font-semibold">
                {me.gmail_email ?? "your Gmail"}
              </span>
            </span>
            <a
              href={CONNECT_GMAIL_URL}
              className="shrink-0 rounded px-1 text-sm font-medium text-violet hover:text-violet-ink hover:underline"
            >
              Use another account
            </a>
          </div>
        ) : (
          <ol className="flex flex-col divide-y divide-line-soft border-y border-line-soft text-[15px]">
            {[
              "Choose the Gmail account on Google's screen",
              "Allow read-only access",
              "Describe what you want to see",
            ].map((label, i) => (
              <Reveal
                as="li"
                key={label}
                index={4 + i}
                className="flex items-center gap-3 py-3.5"
              >
                <span className="grid size-7 shrink-0 place-items-center rounded-full border-2 border-pending-line text-[13px] font-medium text-ink-3 tabular">
                  {i + 1}
                </span>
                <span className="text-ink-2">{label}</span>
              </Reveal>
            ))}
          </ol>
        )}

        {error && (
          <p
            role="alert"
            className="rounded-sm bg-danger-bg px-4 py-3 text-sm text-danger"
          >
            {error}
          </p>
        )}

        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="flex items-center gap-2 text-[13px] text-ink-3">
            <Lock size={14} aria-hidden /> Read-only. Demux never sends or
            changes an email.
          </p>
          {connected ? (
            <Button onClick={onContinue}>
              Continue{" "}
              <ArrowRight
                size={18}
                strokeWidth={2.2}
                aria-hidden
                className="dmx-nudge"
              />
            </Button>
          ) : (
            <ButtonLink href={CONNECT_GMAIL_URL} external>
              Connect Gmail{" "}
              <ArrowRight
                size={18}
                strokeWidth={2.2}
                aria-hidden
                className="dmx-nudge"
              />
            </ButtonLink>
          )}
        </div>
      </div>
    </section>
  );
}
