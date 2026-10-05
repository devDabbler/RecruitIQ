import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { badRequest, CANDIDATE_ID } from "@/lib/forward";
import { getToken } from "@/lib/session";

/**
 * Download everything held about one candidate (pilot plan Track 1 #5).
 *
 * A GET the browser can follow as a plain link, like the CSV export. The API
 * refuses anyone but an administrator and records every download in the
 * audit log; this only carries the session token across.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!CANDIDATE_ID.test(id)) return badRequest("That is not a valid candidate id.");
  const asText = request.nextUrl.searchParams.get("format") === "text";
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ detail: "Sign in to download candidate data." }, { status: 401 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(
      `${API_BASE_URL}/api/candidates/${id}/${asText ? "export.txt" : "export"}`,
      { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" },
    );
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
  const fallbackName = `candidate-data.${asText ? "txt" : "json"}`;
  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": asText ? "text/plain; charset=utf-8" : "application/json",
      "Content-Disposition":
        upstream.headers.get("Content-Disposition") ?? `attachment; filename="${fallbackName}"`,
      "Cache-Control": "no-store",
    },
  });
}
