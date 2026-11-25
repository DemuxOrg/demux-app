/**
 * Sign-up check (server only): may this email create a Demux account?
 *
 * better-auth's `user.create.before` hook (auth.ts) calls this before any account row is
 * written. The API decides from Stripe (subscriptions and reserved trials), free access
 * given in /admin/access, and ADMIN_EMAILS (backend/app/services/access.py), and asks
 * Stripe directly when it doesn't know the email yet. The call is authorized with
 * INTERNAL_API_SECRET, shared with the API.
 *
 * Fails closed: if the API can't answer, nobody gets an account.
 *
 * The errors are 402 / 503, never 403: better-auth turns a 403 from this hook into a fake
 * "check your email" success (it hides whether an address exists), which would leave
 * the user waiting for a code that never comes.
 */
import "server-only";
import { APIError } from "better-auth/api";

const API =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

type Verdict = { allowed: boolean };

async function ask(email: string): Promise<Verdict | null> {
  const secret = process.env.INTERNAL_API_SECRET;
  if (!secret) {
    console.error("INTERNAL_API_SECRET is not set: sign-up is closed.");
    return null;
  }
  try {
    const res = await fetch(`${API}/api/v1/internal/signup-check`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${secret}`,
      },
      body: JSON.stringify({ email }),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (res.ok) return (await res.json()) as Verdict;
    console.error("sign-up check failed: HTTP", res.status);
  } catch (e) {
    console.error("sign-up check failed:", e instanceof Error ? e.message : e);
  }
  return null;
}

export async function assertSignupAllowed(email: string): Promise<void> {
  const verdict = await ask(email);
  if (verdict?.allowed) return;
  if (!verdict)
    throw new APIError("SERVICE_UNAVAILABLE", {
      code: "SIGNUP_UNAVAILABLE",
      message:
        "We can't create accounts right now. Try again in a few minutes.",
    });
  throw new APIError("PAYMENT_REQUIRED", {
    code: "SUBSCRIPTION_REQUIRED",
    message:
      "There's no Demux subscription for this email. Use the email you subscribed with, or subscribe first.",
  });
}
