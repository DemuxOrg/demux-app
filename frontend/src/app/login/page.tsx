/** `/login`: sign in or create an account (email + password, then a 6-digit code). */
import type { Metadata } from "next";
import { Lockup } from "@/components/brand/Logo";
import { PageTransition } from "@/components/motion/PageTransition";
import { AuthFlow } from "@/components/auth/AuthFlow";
import { Reveal } from "@/components/motion/Reveal";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <PageTransition>
      <div className="flex min-h-dvh flex-col">
        <header className="flex items-center px-6 py-5 sm:px-8">
          <Reveal>
            <Lockup size={28} />
          </Reveal>
        </header>
        <main className="flex flex-1 items-center justify-center px-4 pt-4 pb-16">
          <AuthFlow />
        </main>
      </div>
    </PageTransition>
  );
}
