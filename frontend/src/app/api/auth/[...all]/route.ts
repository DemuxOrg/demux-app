/** better-auth's HTTP endpoints (`/api/auth/*`): sign-up, sign-in, sign-out, email codes. */
import { toNextJsHandler } from "better-auth/next-js";
import { auth } from "@/lib/auth";

export const { GET, POST } = toNextJsHandler(auth);
