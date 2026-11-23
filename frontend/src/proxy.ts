/**
 * Optimistic route guard: pages under /workspaces and /profile need a session cookie,
 * otherwise the user goes to /login. This only checks that the cookie exists; the backend
 * validates the session on every API call (a stale cookie gets a 401 and the page sends
 * the user to /login, which this proxy never redirects, so there is no loop).
 */
import { getSessionCookie } from "better-auth/cookies";
import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  if (!getSessionCookie(request, { cookiePrefix: "demux" })) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/", "/workspaces/:path*", "/profile"] };
