import "server-only";

import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "./config";
import { getToken } from "./session";

/**
 * Forward one write to the API with the httpOnly session token (ATS Phase B).
 *
 * The jobs and pipeline handlers each carry their own copy of this; the
 * Phase B routes share this one. The backend's gate is the authority: this
 * passes its status and body through untouched and only refuses a request
 * that has no session at all.
 */
export async function forwardWrite(
  request: NextRequest,
  upstreamPath: string,
  method: "POST" | "PUT" | "DELETE",
): Promise<NextResponse> {
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ detail: "Sign in to make changes." }, { status: 401 });
  }

  const init: RequestInit = {
    method,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  };
  if (method !== "DELETE") {
    let body: unknown = {};
    try {
      body = await request.json();
    } catch {
      // An empty body is allowed; the API validates what it needs.
    }
    init.headers = { ...init.headers, "Content-Type": "application/json" };
    init.body = JSON.stringify(body ?? {});
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}${upstreamPath}`, init);
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  const text = await upstream.text();
  return new NextResponse(text || "{}", {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Path segments the routes accept, checked before anything reaches the API. */
export const NUMERIC_ID = /^\d+$/;
export const USER_ID = /^[0-9a-f-]{36}$/i;
export const STAGE_KEY = /^[a-z0-9_]+$/;
/** ATS Phase C: candidate ids are UUIDs; tags are stored lower-kebab-case. */
export const CANDIDATE_ID = /^[0-9a-f-]{36}$/i;
export const TAG = /^[a-z0-9-]{1,50}$/;

export function badRequest(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 400 });
}
