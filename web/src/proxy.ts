/**
 * Auto-sign-in as the demo user (Phase 3 spec §2).
 *
 * A visitor following a link from Sean's resume should land in a working
 * product, not a login form. Any request without a session cookie gets one
 * here: a server-side call to POST /auth/demo, whose token is set as an
 * httpOnly cookie that page JavaScript cannot read.
 *
 * Named `proxy`, not `middleware`: Next.js 16 renamed the convention. The file
 * must sit next to `app/`, so `src/proxy.ts`.
 */
import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL, COOKIE_SECURE, SESSION_COOKIE } from "./lib/config";

interface DemoTokenResponse {
  access_token: string;
  expires_in: number;
}

export const config = {
  // Everything except Next's own assets and the favicon. Running on static
  // chunks would issue a token per asset request and slow every page load.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.svg$).*)"],
};

export async function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }

  let token: string | null = null;
  let maxAge = 60 * 60 * 24;
  try {
    const response = await fetch(`${API_BASE_URL}/auth/demo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
    if (response.ok) {
      const data = (await response.json()) as DemoTokenResponse;
      token = data.access_token;
      // Outlive the cookie by nothing: matching the JWT's own expiry means the
      // browser drops it exactly when the API would start rejecting it, so the
      // next request mints a fresh one instead of sending a dead token.
      maxAge = data.expires_in ?? maxAge;
    }
  } catch {
    // The API being down is not a reason to refuse to render. Pages handle a
    // missing session by showing their own error state.
  }

  if (!token) return NextResponse.next();

  // Two writes, and both are load-bearing.
  //
  // `request.cookies.set` rewrites the *inbound* cookie header so the Server
  // Components rendering this very request can read the token. Without it the
  // first page view of a session renders signed-out and only the second one
  // works, because `cookies()` reads the request, not the response.
  request.cookies.set(SESSION_COOKIE, token);
  const next = NextResponse.next({ request: { headers: request.headers } });

  // `next.cookies.set` emits Set-Cookie so the browser keeps it for later
  // requests and the proxy stops minting a token per navigation.
  next.cookies.set({
    name: SESSION_COOKIE,
    value: token,
    httpOnly: true,
    secure: COOKIE_SECURE,
    sameSite: "lax",
    path: "/",
    maxAge,
  });
  return next;
}
