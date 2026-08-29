import { NextResponse, type NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/config";
import { getToken } from "@/lib/session";

/**
 * Update or delete one job.
 *
 * Same shape as the create handler: attach the httpOnly session token, let the
 * backend's read-only gate be the authority, pass its status and body through
 * untouched.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function forward(
  request: NextRequest,
  id: string,
  method: "PUT" | "DELETE",
  action: string,
): Promise<NextResponse> {
  const token = await getToken();
  if (!token) {
    return NextResponse.json(
      { detail: `Sign in as an administrator to ${action} jobs.` },
      { status: 401 },
    );
  }

  // A job id is an integer primary key. Rejecting anything else here keeps
  // junk out of the upstream URL entirely.
  if (!/^\d+$/.test(id)) {
    return NextResponse.json({ detail: "That is not a valid job id." }, { status: 400 });
  }

  const init: RequestInit = {
    method,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  };

  if (method === "PUT") {
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json({ detail: "Expected a JSON job payload." }, { status: 400 });
    }
    init.headers = { ...init.headers, "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/jobs/${id}`, init);
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

export async function PUT(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  return forward(request, id, "PUT", "edit");
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  return forward(request, id, "DELETE", "delete");
}
