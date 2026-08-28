import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL, COOKIE_SECURE, SESSION_COOKIE } from "@/lib/config";

/**
 * Exchange admin credentials for a session.
 *
 * A route handler because the httpOnly cookie can only be written server-side.
 * On success the demo cookie is simply overwritten with the admin token; the
 * backend's role claim is what actually grants writes, not anything here.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

interface TokenResponse {
  access_token: string;
  expires_in: number;
  user?: { role?: string };
}

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => null)) as {
    email?: string;
    password?: string;
  } | null;

  if (!body?.email || !body?.password) {
    return NextResponse.json({ detail: "Email and password are required." }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: body.email, password: body.password }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  if (!upstream.ok) {
    const text = await upstream.text();
    let detail = "Sign-in failed";
    try {
      const raw = (JSON.parse(text) as { detail?: unknown }).detail;
      if (typeof raw === "string") {
        detail = raw;
      } else if (Array.isArray(raw)) {
        // FastAPI 422s carry an array of validation objects; flatten to a line.
        detail = raw
          .map((item) => (item as { msg?: string }).msg ?? "invalid input")
          .join("; ");
      }
    } catch {
      /* keep the fallback */
    }
    return NextResponse.json({ detail }, { status: upstream.status });
  }

  const data = (await upstream.json()) as TokenResponse;
  const response = NextResponse.json({ ok: true, role: data.user?.role ?? null });
  response.cookies.set({
    name: SESSION_COOKIE,
    value: data.access_token,
    httpOnly: true,
    secure: COOKIE_SECURE,
    sameSite: "lax",
    path: "/",
    maxAge: data.expires_in ?? 60 * 60 * 24,
  });
  return response;
}
