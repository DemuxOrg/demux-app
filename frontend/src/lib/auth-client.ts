/** Browser side of better-auth: `authClient.signUp.email`, `authClient.emailOtp.*`, … */
import { createAuthClient } from "better-auth/react";
import {
  emailOTPClient,
  inferAdditionalFields,
} from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [
    emailOTPClient(),
    // Mirrors `user.additionalFields` in auth.ts (the server config is server-only).
    inferAdditionalFields({
      user: {
        firstName: { type: "string", required: true },
        lastName: { type: "string", required: true },
      },
    }),
  ],
});
