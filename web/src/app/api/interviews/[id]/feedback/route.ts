import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, NUMERIC_ID } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Submit feedback for an interview. */
export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid interview id.");
  return forwardWrite(request, `/api/interviews/${id}/feedback`, "POST");
}

/** Save the author's draft (Track 2 Phase 4). */
export async function PUT(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid interview id.");
  return forwardWrite(request, `/api/interviews/${id}/feedback`, "PUT");
}
