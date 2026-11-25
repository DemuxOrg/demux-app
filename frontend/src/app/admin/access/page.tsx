"use client";

/**
 * Access (theme.md §8, screen 6): who may sign up and use Demux besides paying customers.
 *
 * - Give free access to an email (beta users, friends), optionally until a date. They
 *   then create their account with that email at /login. Revoking shows the "no access"
 *   screen at their next request; their workspaces are kept.
 * - Stripe customers as the access rule sees them (mirrored by the webhook), with a
 *   "Sync from Stripe" button for the first deploy or after a webhook outage.
 */
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import {
  Card,
  Empty,
  ErrorNote,
  Loading,
  PageHeader,
  Pill,
  dateTime,
  longDate,
  num,
  useAdminData,
} from "@/components/admin/ui";
import {
  ApiError,
  adminApi,
  handleAuthError,
  type AdminCustomer,
  type AdminGrant,
} from "@/lib/api";

const ENDS = [
  { label: "Never", days: 0 },
  { label: "1 month", days: 30 },
  { label: "3 months", days: 90 },
  { label: "1 year", days: 365 },
];

function message(e: unknown): string {
  return e instanceof ApiError || e instanceof Error
    ? e.message
    : "Something went wrong.";
}

function GrantStatus({ status }: { status: string }) {
  if (status === "active") return <Pill tone="success">Active</Pill>;
  if (status === "expired") return <Pill tone="warning">Expired</Pill>;
  return <Pill tone="neutral">Revoked</Pill>;
}

function CustomerStatus({ c }: { c: AdminCustomer }) {
  const label = c.status.replace(/_/g, " ");
  if (c.status === "trialing") return <Pill tone="info">{label}</Pill>;
  if (c.status === "past_due") return <Pill tone="warning">{label}</Pill>;
  if (c.active) return <Pill tone="success">{label}</Pill>;
  if (c.status === "deleted" || c.status === "canceled")
    return <Pill tone="neutral">{label}</Pill>;
  return <Pill tone="warning">{label}</Pill>;
}

function Account({ has }: { has: boolean }) {
  return has ? (
    <span className="text-ink">Signed up</span>
  ) : (
    <span className="text-ink-3">Not yet</span>
  );
}

export default function AdminAccessPage() {
  const { data, error, reload } = useAdminData("access", adminApi.access);
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [days, setDays] = useState(0);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [given, setGiven] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncNote, setSyncNote] = useState<string | null>(null);

  async function give(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    setGiven(null);
    try {
      const g = await adminApi.grantAccess({
        email: email.trim(),
        note: note.trim(),
        expires_at: days
          ? new Date(Date.now() + days * 86_400_000).toISOString()
          : null,
      });
      setGiven(g.email);
      setEmail("");
      setNote("");
      setDays(0);
      reload();
    } catch (err) {
      if (!handleAuthError(err)) setFormError(message(err));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(g: AdminGrant) {
    setRevoking(g.id);
    try {
      await adminApi.revokeAccess(g.id);
      setConfirming(null);
      reload();
    } catch (err) {
      if (!handleAuthError(err)) setFormError(message(err));
    } finally {
      setRevoking(null);
    }
  }

  async function sync() {
    setSyncing(true);
    setSyncNote(null);
    try {
      const { synced } = await adminApi.syncStripe();
      setSyncNote(`Read ${num(synced)} customers from Stripe.`);
      reload();
    } catch (err) {
      if (!handleAuthError(err)) setSyncNote(message(err));
    } finally {
      setSyncing(false);
    }
  }

  if (error) return <ErrorNote message={error} />;
  if (!data) return <Loading />;

  const signupUrl =
    typeof window === "undefined"
      ? "/login?mode=sign-up"
      : `${window.location.origin}/login?mode=sign-up`;

  return (
    <>
      <PageHeader
        title="Access"
        note="Who can sign up and use Demux: paying customers, free access and admins."
      />
      {!data.stripe_configured || !data.webhook_configured ? (
        <ErrorNote
          message={`Stripe is not connected: set ${[
            !data.stripe_configured && "STRIPE_SECRET_KEY",
            !data.webhook_configured && "STRIPE_WEBHOOK_SECRET",
          ]
            .filter(Boolean)
            .join(
              " and ",
            )} on the API. Until then only free access and admins can sign up.`}
        />
      ) : null}

      <Card
        title="Give free access"
        note="For beta users and friends. They create their account with this email."
      >
        <form onSubmit={give} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[2fr_2fr_1fr]">
            <Field
              id="grant-email"
              label="Email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="rana@company.com"
            />
            <Field
              id="grant-note"
              label="Note (optional)"
              maxLength={200}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Beta tester"
            />
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="grant-ends"
                className="text-[13px] font-medium text-ink-2"
              >
                Ends
              </label>
              <select
                id="grant-ends"
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="h-12 rounded-sm border border-line bg-surface px-3 text-base text-ink focus:border-violet-line focus:outline-none"
              >
                {ENDS.map((o) => (
                  <option key={o.days} value={o.days}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[13px] text-ink-3">
              {given ? (
                <>
                  <span className="font-medium text-violet-ink">
                    {given} has access.
                  </span>{" "}
                  Send them {signupUrl}
                </>
              ) : (
                `They sign up at ${signupUrl}`
              )}
            </p>
            <Button type="submit" loading={busy} disabled={!email.trim()}>
              Give access
            </Button>
          </div>
          {formError && <p className="text-sm text-danger">{formError}</p>}
        </form>
      </Card>

      <Card
        title="Free access"
        note={`${num(data.grants.filter((g) => g.status === "active").length)} active`}
      >
        {data.grants.length === 0 ? (
          <Empty>No one has free access yet.</Empty>
        ) : (
          <div className="-mx-[22px] overflow-x-auto px-[22px]">
            <table className="w-full min-w-[860px] text-sm">
              <thead>
                <tr className="text-left text-[13px] text-ink-3">
                  <th scope="col" className="pb-2 font-medium">
                    Email
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Note
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Status
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Account
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Ends
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Granted by
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.grants.map((g) => (
                  <tr key={g.id} className="h-11 border-t border-line-soft">
                    <td className="max-w-[240px] truncate pr-3 font-medium text-ink">
                      {g.email}
                    </td>
                    <td className="max-w-[200px] truncate pr-3 text-ink-2">
                      {g.note || "–"}
                    </td>
                    <td className="pr-3">
                      <GrantStatus status={g.status} />
                    </td>
                    <td className="pr-3">
                      <Account has={g.has_account} />
                    </td>
                    <td className="pr-3 text-ink-2 tabular">
                      {g.status === "revoked"
                        ? `Revoked ${longDate(g.revoked_at)}`
                        : g.expires_at
                          ? longDate(g.expires_at)
                          : "Never"}
                    </td>
                    <td className="max-w-[200px] truncate pr-3 text-ink-3">
                      {g.granted_by ?? "–"}
                    </td>
                    <td className="text-right">
                      {g.status !== "active" ? null : confirming === g.id ? (
                        <span className="inline-flex flex-wrap items-center justify-end gap-2 text-[13px] text-ink-2">
                          Revoke access for {g.email}?
                          <Button
                            variant="quiet"
                            onClick={() => setConfirming(null)}
                          >
                            Cancel
                          </Button>
                          <button
                            type="button"
                            onClick={() => revoke(g)}
                            disabled={revoking === g.id}
                            className="h-11 rounded-full px-3 text-sm font-medium text-danger hover:bg-danger-bg disabled:opacity-40"
                          >
                            Revoke
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirming(g.id)}
                          className="h-11 rounded-full px-3 text-sm font-medium text-danger hover:bg-danger-bg"
                        >
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card
        title="Stripe customers"
        note="Mirrored from Stripe by the webhook. Trialing, active and past-due subscriptions have access."
        right={
          <Button
            variant="quiet"
            loading={syncing}
            disabled={!data.stripe_configured}
            onClick={sync}
          >
            Sync from Stripe
          </Button>
        }
      >
        {syncNote && <p className="mb-3 text-[13px] text-ink-2">{syncNote}</p>}
        {data.customers.length === 0 ? (
          <Empty>No Stripe customers yet.</Empty>
        ) : (
          <div className="-mx-[22px] overflow-x-auto px-[22px]">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="text-left text-[13px] text-ink-3">
                  <th scope="col" className="pb-2 font-medium">
                    Email
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Status
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Trial ends
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Access
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Account
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    Updated
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.customers.map((c) => (
                  <tr key={c.id} className="h-11 border-t border-line-soft">
                    <td
                      className="max-w-[260px] truncate pr-3 font-medium text-ink"
                      title={c.stripe_customer_id}
                    >
                      {c.email || "–"}
                    </td>
                    <td className="pr-3">
                      <CustomerStatus c={c} />
                    </td>
                    <td className="pr-3 text-ink-2 tabular">
                      {c.status === "trialing"
                        ? longDate(c.trial_ends_at)
                        : "–"}
                    </td>
                    <td className="pr-3">
                      {c.active ? (
                        <span className="text-ink">Yes</span>
                      ) : (
                        <span className="text-ink-3">No</span>
                      )}
                    </td>
                    <td className="pr-3">
                      <Account has={c.has_account} />
                    </td>
                    <td className="text-ink-3 tabular">
                      {dateTime(c.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
