import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, NUMERIC_ID } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Edit one feedback template (Track 2 Phase 4). */
export async function PUT(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid template id.");
  return forwardWrite(request, `/api/feedback-templates/${id}`, "PUT");
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid template id.");
  return forwardWrite(request, `/api/feedback-templates/${id}`, "DELETE");
}
