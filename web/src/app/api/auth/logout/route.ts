import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/config";

/**
 * Drop the session cookie. The next navigation arrives cookie-less, so the
 * proxy signs the visitor back in as the read-only demo user automatically.
 * A 303 because the caller is a plain HTML form post.
 */
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const response = NextResponse.redirect(new URL("/", request.url), 303);
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
