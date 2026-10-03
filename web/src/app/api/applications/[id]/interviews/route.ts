import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, NUMERIC_ID } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Assign an interviewer to a stage of this application. A static segment, so
 * Next routes /interviews here rather than to the [action] handler.
 */
export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid application id.");
  return forwardWrite(request, `/api/applications/${id}/interviews`, "POST");
}
