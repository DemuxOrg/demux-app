/**
 * Login (server only): better-auth with email + password and a 6-digit emailed code.
 *
 * - Sign up asks for first name, last name, email and password (`additionalFields`:
 *   `firstName` / `lastName` → `first_name` / `last_name`, which greet the user and are
 *   editable on the profile page through the backend's PATCH /me).
 * - Only an email with access may sign up: a Stripe subscription or reserved trial, free
 *   access from /admin/access, or ADMIN_EMAILS. `databaseHooks.user.create.before` asks
 *   the API (`assertSignupAllowed`, lib/access.ts) before any row is written, whatever
 *   the path that creates the user. The email-code plugin cannot create users.
 * - Sign up creates an unverified user and emails a code (valid 10 minutes). Entering
 *   the code verifies the email and signs the user in. Unverified users cannot sign in:
 *   trying sends a fresh code.
 * - Tables live in the shared Postgres and are created by the backend's Alembic
 *   migrations (`backend/app/models/auth.py`), not by better-auth. The field maps below
 *   point better-auth's camelCase names at our snake_case columns; better-auth checks the
 *   schema on first use.
 * - Sessions are an httpOnly cookie `demux.session_token`, which the FastAPI backend
 *   resolves itself (`backend/app/auth/session.py`). Gmail tokens never touch this code.
 */
import "server-only";
import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { emailOTP } from "better-auth/plugins";
import { Pool } from "pg";
import { assertSignupAllowed } from "./access";
import { OTP_MINUTES, sendOtpEmail } from "./email";

const timestamps = {
  createdAt: "created_at",
  updatedAt: "updated_at",
} as const;
const cookieDomain = process.env.AUTH_COOKIE_DOMAIN;

export const auth = betterAuth({
  appName: "Demux",
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL: process.env.BETTER_AUTH_URL,
  database: new Pool({ connectionString: process.env.AUTH_DATABASE_URL }),

  user: {
    modelName: "users",
    fields: { emailVerified: "email_verified", ...timestamps },
    additionalFields: {
      firstName: {
        type: "string",
        required: true,
        input: true,
        fieldName: "first_name",
      },
      lastName: {
        type: "string",
        required: true,
        input: true,
        fieldName: "last_name",
      },
    },
  },
  session: {
    modelName: "auth_sessions",
    fields: {
      userId: "user_id",
      expiresAt: "expires_at",
      ipAddress: "ip_address",
      userAgent: "user_agent",
      ...timestamps,
    },
    expiresIn: 60 * 60 * 24 * 30, // 30 days
    updateAge: 60 * 60 * 24, // refreshed at most daily
  },
  account: {
    modelName: "auth_accounts",
    fields: {
      userId: "user_id",
      accountId: "account_id",
      providerId: "provider_id",
      accessToken: "access_token",
      refreshToken: "refresh_token",
      idToken: "id_token",
      accessTokenExpiresAt: "access_token_expires_at",
      refreshTokenExpiresAt: "refresh_token_expires_at",
      ...timestamps,
    },
  },
  verification: {
    modelName: "auth_verifications",
    fields: { expiresAt: "expires_at", ...timestamps },
  },

  databaseHooks: {
    user: {
      create: {
        // Paying customers, free access and admins only (see lib/access.ts).
        before: async (user) => {
          await assertSignupAllowed(user.email);
        },
      },
    },
  },

  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true,
    minPasswordLength: 8,
  },
  emailVerification: {
    sendOnSignIn: true,
    autoSignInAfterVerification: true,
  },

  plugins: [
    emailOTP({
      otpLength: 6,
      expiresIn: OTP_MINUTES * 60,
      allowedAttempts: 5,
      sendVerificationOnSignUp: true,
      overrideDefaultEmailVerification: true,
      disableSignUp: true, // accounts are created only by email + password sign-up
      async sendVerificationOTP({ email, otp, type }) {
        // Not awaited by the caller's response timing: a slow mail server must not reveal
        // whether an address has an account.
        sendOtpEmail(email, otp, type).catch((e) =>
          console.error(
            "sign-in code email failed:",
            e instanceof Error ? e.message : e,
          ),
        );
      },
    }),
    nextCookies(), // keep last: lets server actions set the session cookie
  ],

  advanced: {
    cookiePrefix: "demux", // read by the backend: demux.session_token
    database: { generateId: "uuid" },
    ...(cookieDomain
      ? { crossSubDomainCookies: { enabled: true, domain: cookieDomain } }
      : {}),
  },
});
