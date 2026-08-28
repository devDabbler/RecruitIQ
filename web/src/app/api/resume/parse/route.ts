import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Forward a resume to FastAPI's parser.
 *
 * A route handler rather than a Server Component because the file lives in the
 * browser: it has to be POSTed from client JavaScript, and the browser cannot
 * reach uvicorn or read the httpOnly session cookie.
 *
 * `save_to_db` is fixed to false here and never taken from the client. The
 * backend allowlists /api/resume/parse for the demo role only on that
 * condition, and the demo is meant to show the parser, not accumulate
 * strangers' resumes in the database.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_BYTES = 8 * 1024 * 1024;

export async function POST(request: NextRequest) {
  const incoming = await request.formData();
  const file = incoming.get("file");

  if (!(file instanceof File) || file.size === 0) {
    return NextResponse.json({ detail: "Choose a resume file first." }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json(
      { detail: `That file is ${Math.round(file.size / 1024 / 1024)} MB. The limit is 8 MB.` },
      { status: 413 },
    );
  }

  const outgoing = new FormData();
  outgoing.set("file", file, file.name);
  outgoing.set("save_to_db", "false");
  const targetJob = incoming.get("target_job_title");
  if (typeof targetJob === "string" && targetJob) outgoing.set("target_job_title", targetJob);

  const token = await getToken();

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/resume/parse`, {
      method: "POST",
      // Content-Type is deliberately unset: fetch generates the multipart
      // boundary itself, and setting the header by hand omits it, which the
      // server then cannot parse.
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
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
