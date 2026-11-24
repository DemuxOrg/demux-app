"use client";

/** Admin users table (theme.md §7.14): sortable, most expensive first by default. */
import Link from "next/link";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Card,
  Empty,
  ErrorNote,
  GmailPill,
  Loading,
  PageHeader,
  longDate,
  num,
  useAdminData,
  usd,
} from "@/components/admin/ui";
import { adminApi, timeAgo, type AdminUserRow } from "@/lib/api";

type Key =
  | "email"
  | "created_at"
  | "last_active_at"
  | "workspaces"
  | "emails_processed"
  | "emails_received_per_day"
  | "cost_7d"
  | "cost_30d"
  | "needs_reconnect";

const COLUMNS: { key: Key; label: string; numeric?: boolean }[] = [
  { key: "email", label: "User" },
  { key: "created_at", label: "Signed up" },
  { key: "last_active_at", label: "Last active" },
  { key: "workspaces", label: "Workspaces", numeric: true },
  { key: "emails_processed", label: "Emails processed", numeric: true },
  { key: "emails_received_per_day", label: "Received / day", numeric: true },
  { key: "cost_7d", label: "Cost 7d", numeric: true },
  { key: "cost_30d", label: "Cost 30d", numeric: true },
  { key: "needs_reconnect", label: "Gmail" },
];

function value(u: AdminUserRow, key: Key): number | string {
  if (key === "needs_reconnect")
    return u.needs_reconnect ? 2 : u.gmail_connected ? 1 : 0;
  const v = u[key];
  if (v == null) return -1;
  if (key === "created_at" || key === "last_active_at")
    return new Date(String(v)).getTime();
  return typeof v === "string" ? v.toLowerCase() : Number(v);
}

export default function AdminUsersPage() {
  const { data, error } = useAdminData("users", adminApi.users);
  const [sort, setSort] = useState<{ key: Key; desc: boolean }>({
    key: "cost_30d",
    desc: true,
  });

  const rows = useMemo(() => {
    const out = [...(data ?? [])];
    out.sort((a, b) => {
      const x = value(a, sort.key);
      const y = value(b, sort.key);
      const c = x < y ? -1 : x > y ? 1 : 0;
      return sort.desc ? -c : c;
    });
    return out;
  }, [data, sort]);

  return (
    <>
      <PageHeader
        title="Users"
        note={
          data
            ? `${num(data.length)} accounts. Received / day is a 7-day average.`
            : undefined
        }
      />
      {error && <ErrorNote message={error} />}
      {!data ? (
        !error && <Loading />
      ) : (
        <Card>
          {rows.length === 0 ? (
            <Empty>No accounts yet.</Empty>
          ) : (
            <div className="-mx-[22px] overflow-x-auto px-[22px]">
              <table className="w-full min-w-[980px] text-sm">
                <thead>
                  <tr className="text-[13px] text-ink-3">
                    {COLUMNS.map((c) => {
                      const active = sort.key === c.key;
                      const Icon =
                        active && !sort.desc ? ChevronUp : ChevronDown;
                      return (
                        <th
                          key={c.key}
                          scope="col"
                          aria-sort={
                            active
                              ? sort.desc
                                ? "descending"
                                : "ascending"
                              : "none"
                          }
                          className={`pb-2 font-medium ${c.numeric ? "text-right" : "text-left"}`}
                        >
                          <button
                            type="button"
                            onClick={() =>
                              setSort((s) => ({
                                key: c.key,
                                desc:
                                  s.key === c.key
                                    ? !s.desc
                                    : c.numeric !== false && c.key !== "email",
                              }))
                            }
                            className={`inline-flex h-8 items-center gap-1 rounded-full hover:text-ink focus-visible:ring-[3px] focus-visible:ring-violet/25 ${
                              active ? "text-ink" : ""
                            }`}
                          >
                            {c.label}
                            <Icon
                              size={14}
                              aria-hidden
                              className={active ? "" : "opacity-0"}
                            />
                          </button>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((u) => (
                    <tr key={u.id} className="h-11 border-t border-line-soft">
                      <td className="max-w-[260px] py-2 pr-4">
                        <Link
                          href={`/admin/users/${u.id}`}
                          className="block truncate font-medium text-ink hover:text-violet-ink hover:underline"
                        >
                          {u.email}
                        </Link>
                        {u.name && (
                          <span className="block truncate text-[13px] text-ink-3">
                            {u.name}
                          </span>
                        )}
                      </td>
                      <td className="pr-4 text-ink-2">
                        {longDate(u.created_at)}
                      </td>
                      <td className="pr-4 text-ink-2">
                        {u.last_active_at ? timeAgo(u.last_active_at) : "–"}
                      </td>
                      <td className="tabular pr-4 text-right">
                        {num(u.workspaces)}
                      </td>
                      <td className="tabular pr-4 text-right">
                        {num(u.emails_processed)}
                      </td>
                      <td className="tabular pr-4 text-right">
                        {u.emails_received_per_day == null
                          ? "–"
                          : num(u.emails_received_per_day)}
                      </td>
                      <td className="tabular pr-4 text-right">
                        {usd(u.cost_7d)}
                      </td>
                      <td className="tabular pr-4 text-right font-medium">
                        {usd(u.cost_30d)}
                      </td>
                      <td>
                        <GmailPill
                          connected={u.gmail_connected}
                          needsReconnect={u.needs_reconnect}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
