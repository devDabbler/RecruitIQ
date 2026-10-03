import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, NUMERIC_ID } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Context = { params: Promise<{ id: string }> };

/**
 * Create or replace (POST) and turn off (DELETE) a candidate's status link
 * (ATS Phase E). A static segment, so Next routes it here rather than to the
 * [action] handler.
 */
async function handle(request: NextRequest, context: Context, method: "POST" | "DELETE") {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid application id.");
  return forwardWrite(request, `/api/applications/${id}/status-link`, method);
}

export async function POST(request: NextRequest, context: Context) {
  return handle(request, context, "POST");
}

export async function DELETE(request: NextRequest, context: Context) {
  return handle(request, context, "DELETE");
}
