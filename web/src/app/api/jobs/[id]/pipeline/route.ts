import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, NUMERIC_ID } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Save the stage editor: remove, toggle, rename, reorder, add (ATS Phase E). */
export async function PUT(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid job id.");
  return forwardWrite(request, `/api/jobs/${id}/pipeline`, "PUT");
}
