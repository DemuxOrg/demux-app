/**
 * Privacy policy (public). Plain statements of what Demux does with Gmail data; keep it
 * in sync with the code (backend/app/services/admin.py, app/auth/google.py) and have it
 * reviewed before launch.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { Lockup } from "@/components/brand/Logo";

export const metadata: Metadata = { title: "Privacy" };

const SECTIONS: { title: string; body: string[] }[] = [
  {
    title: "What Demux reads",
    body: [
      "When you connect Gmail, Demux asks Google for read-only access. It reads the emails that match the workspaces you create, to extract the records you asked for. Demux never sends, deletes or changes an email.",
      "Your Google tokens are stored encrypted on our servers and are never shown to your browser or to Demux staff.",
    ],
  },
  {
    title: "How your email is processed",
    body: [
      "Matching emails are sent to an AI model provider to extract records. The results (your workspace's records) are stored in your account. Our logs contain ids, counts and costs, never email content.",
      "Once a day Demux counts how many emails your inbox received, using message ids only. It does not open those messages.",
    ],
  },
  {
    title: "What Demux staff can see",
    body: [
      "Demux staff can see the prompts you write and usage statistics to operate and improve the product.",
      "Usage statistics are counts, AI token usage and costs, run statuses and dates. Staff can also see the messages you type in a workspace's chat. Staff cannot see your emails, their subjects or senders, the records extracted from them, or your workspace's interface. Every staff view is logged.",
    ],
  },
  {
    title: "Deleting your data",
    body: [
      "You can disconnect Gmail from your profile at any time; your workspaces then stop updating. Deleting your account deletes your workspaces, records and runs. You can also remove Demux's access at myaccount.google.com/permissions.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="px-6 pt-[18px]">
        <Link
          href="/"
          aria-label="Demux home"
          className="inline-block rounded-full"
        >
          <Lockup size={28} />
        </Link>
      </header>
      <main className="mx-auto w-full max-w-[720px] px-6 py-10">
        <article className="rounded-xl bg-surface px-7 py-8 shadow-panel">
          <h1 className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em] text-ink">
            Privacy
          </h1>
          <p className="mt-2 text-[13px] text-ink-3">
            Last updated November 23, 2026
          </p>
          {SECTIONS.map((s) => (
            <section key={s.title} className="mt-7">
              <h2 className="text-[18px] font-semibold tracking-[-0.015em] text-ink">
                {s.title}
              </h2>
              {s.body.map((p) => (
                <p key={p} className="mt-2 text-base text-pretty text-ink-2">
                  {p}
                </p>
              ))}
            </section>
          ))}
        </article>
      </main>
    </div>
  );
}
