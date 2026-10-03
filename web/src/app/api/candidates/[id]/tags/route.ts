import type { NextRequest } from "next/server";

import { badRequest, CANDIDATE_ID, forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Tag a candidate (ATS Phase C). The API normalizes the tag. */
export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!CANDIDATE_ID.test(id)) return badRequest("That is not a valid candidate id.");
  return forwardWrite(request, `/api/candidates/${id}/tags`, "POST");
}
