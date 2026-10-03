import type { NextRequest } from "next/server";

import { badRequest, CANDIDATE_ID, forwardWrite, TAG } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Remove one tag from a candidate (ATS Phase C). */
export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ id: string; tag: string }> },
) {
  const { id, tag } = await context.params;
  if (!CANDIDATE_ID.test(id) || !TAG.test(tag)) return badRequest("That is not a valid tag.");
  return forwardWrite(request, `/api/candidates/${id}/tags/${tag}`, "DELETE");
}
