/**
 * Transactional email (server only): the 6-digit sign-in code.
 *
 * Sent over SMTP from EMAIL_FROM (default "Demux <support@usedemux.com>"). Without
 * SMTP_HOST, codes are printed to the server log in development and refused in
 * production, so a misconfigured deploy fails loudly instead of locking users out.
 */
import "server-only";
import { createTransport, type Transporter } from "nodemailer";

const FROM = process.env.EMAIL_FROM || "Demux <support@usedemux.com>";
export const OTP_MINUTES = 10;

let transport: Transporter | null = null;

function smtp(): Transporter | null {
  if (!process.env.SMTP_HOST) return null;
  transport ??= createTransport({
    host: process.env.SMTP_HOST,
    port: Number(process.env.SMTP_PORT || 587),
    // 465 is implicit TLS; 587 upgrades with STARTTLS.
    secure: Number(process.env.SMTP_PORT || 587) === 465,
    auth: process.env.SMTP_USER
      ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASSWORD }
      : undefined,
  });
  return transport;
}

const SUBJECTS = {
  "email-verification": "Your Demux verification code",
  "sign-in": "Your Demux sign-in code",
  "forget-password": "Your Demux password reset code",
  "change-email": "Confirm your new Demux email",
} as const;

export type OtpKind = keyof typeof SUBJECTS;

function html(otp: string): string {
  // Email clients ignore most CSS: inline styles, system font, brand colors only.
  return `<!doctype html><html><body style="margin:0;background:#F4F7FB;padding:40px 16px;font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;color:#0C1A2E">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;background:#FFFFFF;border:1px solid #E6EBF2;border-radius:20px">
<tr><td style="padding:32px 32px 8px;font-size:19px;font-weight:600;letter-spacing:-0.02em">Demux</td></tr>
<tr><td style="padding:8px 32px 0;font-size:16px;line-height:1.5;color:#33445C">Enter this code to continue. It expires in ${OTP_MINUTES} minutes.</td></tr>
<tr><td style="padding:20px 32px"><div style="display:inline-block;padding:14px 20px;border-radius:12px;background:#EEE9FE;color:#4B24C9;font-size:30px;font-weight:600;letter-spacing:0.18em;font-variant-numeric:tabular-nums">${otp}</div></td></tr>
<tr><td style="padding:0 32px 32px;font-size:13px;line-height:1.45;color:#5B6B80">If you didn't ask for this code, you can ignore this email. Someone may have typed your address by mistake.</td></tr>
</table></td></tr></table></body></html>`;
}

export async function sendOtpEmail(
  to: string,
  otp: string,
  kind: OtpKind,
): Promise<void> {
  const t = smtp();
  if (!t) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("SMTP_HOST is not set: cannot send sign-in codes.");
    }
    // Dev only: no mail server configured.
    console.info(`[demux dev] ${kind} code for ${to}: ${otp}`);
    return;
  }
  await t.sendMail({
    from: FROM,
    to,
    subject: SUBJECTS[kind],
    text: `Your Demux code is ${otp}. It expires in ${OTP_MINUTES} minutes.\n\nIf you didn't ask for this code, you can ignore this email.`,
    html: html(otp),
  });
}
