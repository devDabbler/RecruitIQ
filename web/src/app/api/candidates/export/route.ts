import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Download the filtered candidate list as CSV (ATS Phase C).
 *
 * A GET the browser can follow as a plain link. The token lives in an
 * httpOnly cookie, so the browser cannot call FastAPI directly.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const PASSED_THROUGH = ["keyword", "status", "job_id"];

export async function GET(request: NextRequest) {
  const query = new URLSearchParams();
  for (const key of PASSED_THROUGH) {
    const value = request.nextUrl.searchParams.get(key);
    if (value) query.set(key, value);
  }
  // Track 2 Phase 5: every tag, since all of them must match.
  for (const tag of request.nextUrl.searchParams.getAll("tag")) {
    if (tag) query.append("tag", tag);
  }
  const token = await getToken();

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/candidates/export.csv?${query}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  if (!upstream.ok) {
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  }
  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition":
        upstream.headers.get("Content-Disposition") ?? 'attachment; filename="candidates.csv"',
    },
  });
}
