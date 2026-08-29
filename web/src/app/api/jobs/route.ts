import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Create a job.
 *
 * A route handler rather than a Server Action because the form is a client
 * component that needs the failure body back to render field-level errors, and
 * because the session JWT lives in an httpOnly cookie the browser cannot read
 * and attach itself.
 *
 * No local authorisation beyond requiring a token: the backend's read-only gate
 * decides, and its 401/403 bodies pass straight through so the form can explain
 * the refusal instead of showing a generic failure.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const token = await getToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Sign in as an administrator to create jobs." },
      { status: 401 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Expected a JSON job payload." }, { status: 400 });
  }

  let upstream: Response;
  try {
    // Trailing slash matters: FastAPI 307-redirects /api/jobs to /api/jobs/,
    // and a redirected POST can arrive without its Authorization header.
    upstream = await fetch(`${API_BASE_URL}/api/jobs/`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
