import type { NextRequest } from "next/server";

import { badRequest, forwardRead, NUMERIC_ID } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** An AI brief of this application's submitted feedback (Track 2 Phase 6). Never stored. */
export async function GET(_request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid application id.");
  return forwardRead(`/api/applications/${id}/feedback-summary`);
}
