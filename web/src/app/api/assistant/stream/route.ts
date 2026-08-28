import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Pipe the assistant's SSE stream from FastAPI to the browser.
 *
 * This is the one place a route handler earns its keep. Everywhere else, Server
 * Components call the API directly — but a chat turn is client-initiated and
 * arrives incrementally, and the browser cannot reach uvicorn (it binds
 * loopback) nor read the httpOnly session cookie to authenticate itself. So the
 * handler attaches the token and forwards the body untouched.
 *
 * Nothing is buffered or re-encoded: `response.body` is handed straight back as
 * the response stream. Reading it into a string here would collapse the whole
 * point of the feature — the tool activity would arrive at the same moment as
 * the answer it was supposed to fill the wait for (spec §5).
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const body = await request.text();
  const token = await getToken();

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/assistant/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body,
      // Abort the upstream turn when the user navigates away, rather than
      // leaving a model call running against a socket nobody is reading.
      signal: request.signal,
      cache: "no-store",
      // Node's fetch requires this to stream a request body; harmless here and
      // needed the moment the payload grows past a single chunk.
      duplex: "half",
    } as RequestInit & { duplex: "half" });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the API at ${API_BASE_URL}. Is uvicorn running?` },
      { status: 503 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    return NextResponse.json(
      { detail: await upstream.text().catch(() => "Assistant request failed") },
      { status: upstream.status || 502 },
    );
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
