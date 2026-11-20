"use client";

/**
 * Profile (`/profile`, theme.md §8.6): first and last name (saved with PATCH /me; the
 * create page greets the user with the first name), the sign-in email, and the Gmail
 * Demux reads: connect, reconnect, switch accounts (Google sends the user back here) or
 * disconnect (asks first, inline; workspaces stay but stop syncing).
 */
import { Check, Lock } from "lucide-react";
import { useState } from "react";
import { Reveal, RevealText } from "@/components/motion/Reveal";
import { useShell } from "@/components/shell/AppShell";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/Spinner";
import { api, ApiError, handleAuthError, type Me } from "@/lib/api";
import { connectGmailUrl, useGmailReturn } from "@/lib/gmail";

const card = "rounded-xl bg-surface px-6 py-6 shadow-panel sm:px-7";

export function ProfileScreen() {
  const { me } = useShell();
  const gmail = useGmailReturn();

  return (
    <main className="px-4 pt-[clamp(80px,12vh,128px)] pb-16">
      <div className="mx-auto flex w-full max-w-[640px] flex-col gap-6">
        <div className="flex flex-col gap-2 px-1">
          <RevealText
            text="Profile"
            className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em]"
          />
          <Reveal as="p" index={1} className="text-base text-ink-on-sky">
            Your name and the Gmail Demux reads.
          </Reveal>
        </div>
        {me ? (
          <>
            <Reveal index={2}>
              <NameCard me={me} />
            </Reveal>
            <Reveal index={3}>
              <AccountCard me={me} gmail={gmail} />
            </Reveal>
          </>
        ) : (
          <div className="grid place-items-center py-16" aria-label="Loading">
            <Reveal delay={250}>
              <Spinner size={28} />
            </Reveal>
          </div>
        )}
      </div>
    </main>
  );
}

function NameCard({ me }: { me: Me }) {
  const { reload } = useShell();
  const [first, setFirst] = useState(me.first_name);
  const [last, setLast] = useState(me.last_name);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const changed =
    first.trim() !== me.first_name || last.trim() !== me.last_name;
  const valid = !!first.trim() && !!last.trim();

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!changed || !valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.updateMe({ first_name: first.trim(), last_name: last.trim() });
      await reload(); // the sidebar and the greeting use the new name
      setSaved(true);
    } catch (err) {
      if (!handleAuthError(err))
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't save your name. Try again.",
        );
    } finally {
      setBusy(false);
    }
  }

  function edit(set: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      set(e.target.value);
      setSaved(false);
    };
  }

  return (
    <form onSubmit={save} className={`${card} flex flex-col gap-5`}>
      <div className="flex flex-col gap-1">
        <h2 className="text-[15px] font-semibold">Your name</h2>
        <p className="text-[13px] text-ink-3">
          Demux greets you by your first name.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field
          id="profile-first-name"
          label="First name"
          autoComplete="given-name"
          required
          maxLength={100}
          value={first}
          onChange={edit(setFirst)}
        />
        <Field
          id="profile-last-name"
          label="Last name"
          autoComplete="family-name"
          required
          maxLength={100}
          value={last}
          onChange={edit(setLast)}
        />
      </div>
      {error && (
        <p
          role="alert"
          className="rounded-sm bg-danger-bg px-4 py-3 text-sm text-danger"
        >
          {error}
        </p>
      )}
      <div className="flex items-center justify-end gap-3">
        <p
          role="status"
          className={`flex items-center gap-1.5 text-[13px] text-violet-ink transition-opacity duration-200 ease-dmx ${saved ? "opacity-100" : "opacity-0"}`}
        >
          {saved && (
            <>
              <Check size={14} strokeWidth={2.4} aria-hidden /> Saved
            </>
          )}
        </p>
        <Button
          type="submit"
          size="sm"
          loading={busy}
          disabled={!changed || !valid}
        >
          Save
        </Button>
      </div>
    </form>
  );
}

function AccountCard({
  me,
  gmail,
}: {
  me: Me;
  gmail: { connected: boolean; error: string | null };
}) {
  const { reload } = useShell();
  const connected = me.gmail_connected && !me.needs_reconnect;
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The dev fake mailbox reports "connected" with no address: nothing to disconnect.
  const canDisconnect = me.gmail_connected && !!me.gmail_email;

  async function disconnect() {
    setBusy(true);
    setError(null);
    try {
      await api.disconnectGmail();
      await reload(); // the sidebar and the create page follow
      setConfirming(false);
    } catch (err) {
      if (!handleAuthError(err))
        setError(
          err instanceof ApiError
            ? err.message
            : "Couldn't disconnect Gmail. Try again.",
        );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`${card} flex flex-col`} aria-labelledby="account">
      <h2 id="account" className="text-[15px] font-semibold">
        Account
      </h2>
      <dl className="mt-2 flex flex-col divide-y divide-line-soft">
        <div className="flex flex-col gap-1 py-4">
          <dt className="text-[13px] text-ink-3">Sign-in email</dt>
          <dd className="truncate text-[15px] font-medium">{me.email}</dd>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3 py-4">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <dt className="text-[13px] text-ink-3">Gmail Demux reads</dt>
            <dd className="truncate text-[15px] font-medium">
              {me.gmail_connected
                ? (me.gmail_email ?? "Connected")
                : "Not connected"}
            </dd>
            {me.needs_reconnect ? (
              <dd className="text-[13px] text-danger">
                Disconnected. Reconnect to keep your workspaces updated.
              </dd>
            ) : (
              gmail.connected &&
              me.gmail_connected && (
                <dd className="flex items-center gap-1.5 text-[13px] text-violet-ink">
                  <Check size={14} strokeWidth={2.4} aria-hidden /> Connected
                </dd>
              )
            )}
          </div>
          {confirming ? (
            <div className="flex w-full flex-wrap items-center justify-end gap-3">
              <p className="mr-auto text-[13px] text-ink-2">
                Disconnect {me.gmail_email}? Your workspaces stay but stop
                updating.
              </p>
              <Button
                variant="quiet"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                Cancel
              </Button>
              <Button
                variant="quiet"
                loading={busy}
                onClick={disconnect}
                className="text-danger hover:text-danger"
              >
                Disconnect
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {canDisconnect && (
                <Button variant="quiet" onClick={() => setConfirming(true)}>
                  Disconnect
                </Button>
              )}
              <ButtonLink
                href={connectGmailUrl("profile")}
                external
                variant="quiet"
              >
                {me.needs_reconnect
                  ? "Reconnect Gmail"
                  : connected
                    ? "Use another account"
                    : "Connect Gmail"}
              </ButtonLink>
            </div>
          )}
        </div>
      </dl>
      {(error ?? gmail.error) && (
        <p
          role="alert"
          className="mb-3 rounded-sm bg-danger-bg px-4 py-3 text-sm text-danger"
        >
          {error ?? gmail.error}
        </p>
      )}
      <p className="flex items-center gap-2 border-t border-line-soft pt-4 text-[13px] text-ink-3">
        <Lock size={14} aria-hidden /> Read-only. Demux never sends or changes
        an email.
      </p>
    </section>
  );
}
