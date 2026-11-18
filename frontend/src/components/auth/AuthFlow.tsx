"use client";

/**
 * Sign in / create account, then the 6-digit email code.
 *
 * - Create account: email + password → better-auth creates an unverified user and
 *   emails a code → "Check your email" → the right code verifies the email and signs in.
 * - Sign in: email + password. An unverified account gets a fresh code (better-auth
 *   sends it) and goes to the code step.
 * The sign-in email can differ from the Gmail connected later.
 */
import { ArrowRight, Eye, EyeOff, Lock } from "lucide-react";
import { useRouter } from "next/navigation";
import { startTransition, useEffect, useState } from "react";
import { LogoMark } from "@/components/brand/Logo";
import { StepTransition } from "@/components/motion/PageTransition";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { authClient } from "@/lib/auth-client";
import { CODE_LENGTH, CodeInput } from "./CodeInput";

type Mode = "sign-in" | "sign-up";
type Step = "credentials" | "code";

const RESEND_AFTER_S = 30;

const MESSAGES: Record<string, string> = {
  INVALID_EMAIL_OR_PASSWORD: "That email and password don't match.",
  INVALID_EMAIL: "Enter a valid email address.",
  USER_ALREADY_EXISTS:
    "There's already an account with this email. Sign in instead.",
  USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL:
    "There's already an account with this email. Sign in instead.",
  PASSWORD_TOO_SHORT: "Use at least 8 characters for your password.",
  PASSWORD_TOO_LONG: "That password is too long.",
  INVALID_OTP: "That code isn't right. Check the latest email from Demux.",
  OTP_EXPIRED: "That code expired. Send a new one.",
  TOO_MANY_ATTEMPTS: "Too many tries with this code. Send a new one.",
};

function message(error: {
  code?: string;
  message?: string;
  status?: number;
}): string {
  if (error.status === 429)
    return "Too many attempts. Wait a minute, then try again.";
  return (
    (error.code && MESSAGES[error.code]) ||
    error.message ||
    "Something went wrong. Try again."
  );
}

export function AuthFlow() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("sign-in");
  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resendIn, setResendIn] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  // Already signed in (e.g. back button): go straight to the workspaces.
  useEffect(() => {
    authClient.getSession().then(({ data }) => {
      if (data?.session) router.replace("/workspaces");
    });
  }, [router]);

  useEffect(() => {
    if (resendIn <= 0) return;
    const t = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [resendIn]);

  function goTo(next: Step) {
    setError(null);
    setNotice(null);
    startTransition(() => setStep(next));
  }

  function toCodeStep() {
    setCode("");
    setResendIn(RESEND_AFTER_S);
    goTo("code");
  }

  async function submitCredentials(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const address = email.trim().toLowerCase();
    if (mode === "sign-up") {
      const { error } = await authClient.signUp.email({
        email: address,
        password,
        name: address.split("@")[0],
      });
      setBusy(false);
      if (error) {
        setError(message(error));
        if (error.code?.startsWith("USER_ALREADY_EXISTS")) setMode("sign-in");
        return;
      }
      toCodeStep();
      return;
    }
    const { error } = await authClient.signIn.email({
      email: address,
      password,
    });
    if (error) {
      setBusy(false);
      if (error.code === "EMAIL_NOT_VERIFIED") {
        toCodeStep();
        return;
      }
      setError(message(error));
      return;
    }
    router.push("/workspaces");
  }

  async function verify(value = code) {
    if (value.length !== CODE_LENGTH || busy) return;
    setBusy(true);
    setError(null);
    const { error } = await authClient.emailOtp.verifyEmail({
      email: email.trim().toLowerCase(),
      otp: value,
    });
    if (error) {
      setBusy(false);
      setError(message(error));
      return;
    }
    router.push("/workspaces");
  }

  async function resend() {
    setError(null);
    setNotice(null);
    setResendIn(RESEND_AFTER_S);
    const { error } = await authClient.emailOtp.sendVerificationOtp({
      email: email.trim().toLowerCase(),
      type: "email-verification",
    });
    if (error) setError(message(error));
    else {
      setCode("");
      setNotice("We sent a new code. Earlier codes no longer work.");
    }
  }

  const signUp = mode === "sign-up";

  return (
    <div className="w-full max-w-[440px]">
      <StepTransition stepKey={step}>
        <section className="rounded-2xl bg-surface px-7 pt-8 pb-7 shadow-float sm:px-9 sm:pt-9">
          {step === "credentials" ? (
            <form
              onSubmit={submitCredentials}
              className="flex flex-col gap-6"
              noValidate
            >
              <div className="flex flex-col gap-4">
                <LogoMark size={46} />
                <div className="flex flex-col gap-2">
                  <h1 className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em]">
                    {signUp ? "Create your account" : "Sign in to Demux"}
                  </h1>
                  <p className="text-base text-ink-2">
                    {signUp
                      ? "Use any email. It doesn't have to be the Gmail you'll connect."
                      : "Welcome back. Use the email and password you signed up with."}
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-4">
                <Field
                  id="email"
                  label="Email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                />
                <Field
                  id="password"
                  label="Password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={signUp ? "new-password" : "current-password"}
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  hint={signUp ? "At least 8 characters." : undefined}
                  trailing={
                    <button
                      type="button"
                      onClick={() => setShowPassword((s) => !s)}
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
                      className="grid size-11 place-items-center rounded-full text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink"
                    >
                      {showPassword ? (
                        <EyeOff size={18} aria-hidden />
                      ) : (
                        <Eye size={18} aria-hidden />
                      )}
                    </button>
                  }
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

              <div className="flex flex-col gap-4">
                <Button
                  type="submit"
                  loading={busy}
                  disabled={!email.trim() || password.length < (signUp ? 8 : 1)}
                  className="w-full"
                >
                  {signUp ? "Create account" : "Sign in"}
                  <ArrowRight size={18} strokeWidth={2.2} aria-hidden />
                </Button>
                <p className="text-center text-sm text-ink-2">
                  {signUp ? "Already have an account? " : "New to Demux? "}
                  <button
                    type="button"
                    onClick={() => {
                      setError(null);
                      setMode(signUp ? "sign-in" : "sign-up");
                    }}
                    className="rounded font-medium text-violet hover:text-violet-ink hover:underline"
                  >
                    {signUp ? "Sign in" : "Create an account"}
                  </button>
                </p>
              </div>
            </form>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                verify();
              }}
              className="flex flex-col gap-6"
            >
              <div className="flex flex-col gap-4">
                <LogoMark size={46} />
                <div className="flex flex-col gap-2">
                  <h1 className="text-[30px] leading-[1.1] font-medium tracking-[-0.03em]">
                    Check your email
                  </h1>
                  <p className="text-base text-ink-2">
                    We sent a 6-digit code to{" "}
                    <span className="font-medium break-words text-ink">
                      {email.trim()}
                    </span>
                    . It expires in 10 minutes.
                  </p>
                </div>
              </div>

              <CodeInput
                value={code}
                onChange={(v) => {
                  setCode(v);
                  if (error) setError(null);
                }}
                onComplete={verify}
                invalid={!!error}
                disabled={busy}
              />

              {error && (
                <p
                  role="alert"
                  className="rounded-sm bg-danger-bg px-4 py-3 text-sm text-danger"
                >
                  {error}
                </p>
              )}
              {notice && !error && (
                <p
                  role="status"
                  className="rounded-sm bg-violet-soft px-4 py-3 text-sm text-violet-ink"
                >
                  {notice}
                </p>
              )}

              <div className="flex flex-col gap-4">
                <Button
                  type="submit"
                  loading={busy}
                  disabled={code.length !== CODE_LENGTH}
                  className="w-full"
                >
                  Verify
                </Button>
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <button
                    type="button"
                    onClick={resend}
                    disabled={resendIn > 0}
                    className="rounded font-medium text-violet tabular hover:text-violet-ink hover:underline disabled:cursor-not-allowed disabled:text-ink-3 disabled:no-underline"
                  >
                    {resendIn > 0
                      ? `Resend code in ${resendIn}s`
                      : "Resend code"}
                  </button>
                  <button
                    type="button"
                    onClick={() => goTo("credentials")}
                    className="rounded text-ink-2 hover:text-ink hover:underline"
                  >
                    Use a different email
                  </button>
                </div>
              </div>
            </form>
          )}
        </section>
      </StepTransition>
      <p className="mt-5 flex items-center justify-center gap-2 text-[13px] text-ink-on-sky">
        <Lock size={14} aria-hidden /> Read-only. Demux never sends or changes
        an email.
      </p>
    </div>
  );
}
