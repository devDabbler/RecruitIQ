import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Forward a pipeline action to the API with the httpOnly session token.
 *
 * Same shape as the jobs handlers: the backend's read-only gate is the
 * authority; this passes its status and body through untouched.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const ACTIONS = new Set(["advance", "skip", "reject", "decline"]);

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string; action: string }> },
) {
  const { id, action } = await context.params;
  if (!/^\d+$/.test(id)) {
    return NextResponse.json({ detail: "That is not a valid application id." }, { status: 400 });
  }
  if (!ACTIONS.has(action)) {
    return NextResponse.json({ detail: `Unknown action '${action}'.` }, { status: 404 });
  }

  const token = await getToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Sign in to move candidates." },
      { status: 401 },
    );
  }

  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    // An empty body is fine: every action works without a note.
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/applications/${id}/${action}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
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
