import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Forward a reviewed parse to FastAPI's save-candidate endpoint.
 *
 * No anonymous retry here, unlike the parse route: saving is a write, and the
 * backend's read-only gate refusing the demo role is the entire point. The 401
 * and 403 bodies pass through so the screen can say why the save was refused.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const incoming = await request.formData();
  const file = incoming.get("file");
  const parsed = incoming.get("parsed_data");

  if (!(file instanceof File) || file.size === 0) {
    return NextResponse.json({ detail: "The original resume file is required." }, { status: 400 });
  }
  if (typeof parsed !== "string" || !parsed) {
    return NextResponse.json({ detail: "Parse the resume before saving it." }, { status: 400 });
  }

  const token = await getToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Sign in as an administrator to save candidates." },
      { status: 401 },
    );
  }

  const outgoing = new FormData();
  outgoing.set("file", file, file.name);
  outgoing.set("parsed_data", parsed);
  const position = incoming.get("position_applied");
  if (typeof position === "string" && position) outgoing.set("position_applied", position);

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/resume/save-candidate`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: outgoing,
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
