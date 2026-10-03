import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, NUMERIC_ID, STAGE_KEY } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Replace a stage's default interviewers. */
export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ id: string; stage: string }> },
) {
  const { id, stage } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid job id.");
  if (!STAGE_KEY.test(stage)) return badRequest("That is not a valid stage.");
  return forwardWrite(request, `/api/jobs/${id}/stages/${stage}/default-interviewers`, "PUT");
}
