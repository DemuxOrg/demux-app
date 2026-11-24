"use client";

/** A workspace's runs and the edit-chat messages that triggered some of them. */
import type { AdminRun, AdminWorkspace } from "@/lib/api";
import { Empty, Pill, dateTime, duration, num, statusTone, usd } from "./ui";

const KIND: Record<string, string> = {
  build: "Build",
  sync: "Sync",
  edit: "Edit",
};

export function RunsTable({ runs }: { runs: AdminRun[] }) {
  if (!runs.length) return <Empty>No runs.</Empty>;
  return (
    <div className="-mx-[22px] overflow-x-auto px-[22px]">
      <table className="w-full min-w-[760px] text-sm">
        <thead>
          <tr className="text-[13px] text-ink-3">
            <th scope="col" className="pb-2 text-left font-medium">
              Run
            </th>
            <th scope="col" className="pb-2 text-left font-medium">
              Status
            </th>
            <th scope="col" className="pb-2 text-left font-medium">
              Started
            </th>
            <th scope="col" className="pb-2 text-right font-medium">
              Duration
            </th>
            <th scope="col" className="pb-2 text-right font-medium">
              Tokens in
            </th>
            <th scope="col" className="pb-2 text-right font-medium">
              Tokens out
            </th>
            <th scope="col" className="pb-2 text-right font-medium">
              Cost
            </th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="h-11 border-t border-line-soft">
              <td className="pr-4 font-medium text-ink">
                {KIND[r.kind] ?? r.kind}
              </td>
              <td className="pr-4">
                <span className="inline-flex items-center gap-2">
                  <Pill tone={statusTone(r.status)}>{r.status}</Pill>
                  {r.error_code && (
                    <span className="text-[13px] text-ink-3">
                      {r.error_code}
                    </span>
                  )}
                </span>
              </td>
              <td className="pr-4 text-ink-2">{dateTime(r.created_at)}</td>
              <td className="tabular pr-4 text-right text-ink-2">
                {duration(r.duration_s)}
              </td>
              <td className="tabular pr-4 text-right">{num(r.input_tokens)}</td>
              <td className="tabular pr-4 text-right">
                {num(r.output_tokens)}
              </td>
              <td className="tabular text-right font-medium">
                {usd(r.cost_usd)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EditsList({ edits }: { edits: AdminWorkspace["edits"] }) {
  if (!edits.length) return <Empty>No edit messages.</Empty>;
  return (
    <ul className="flex flex-col">
      {edits.map((e) => (
        <li
          key={e.run_id}
          className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 border-t border-line-soft py-3 first:border-t-0"
        >
          <p className="min-w-0 flex-1 text-[15px] text-pretty text-ink">
            “{e.text}”
          </p>
          <span className="flex items-center gap-2 text-[13px] text-ink-3">
            {dateTime(e.created_at)}
            <Pill tone={statusTone(e.status)}>edit run {e.status}</Pill>
          </span>
        </li>
      ))}
    </ul>
  );
}
