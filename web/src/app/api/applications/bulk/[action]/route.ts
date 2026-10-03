import { NextResponse, type NextRequest } from "next/server";

import { forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const ACTIONS = new Set(["advance", "reject"]);

/**
 * Bulk advance or reject (ATS Phase C). A static `bulk` segment beats the
 * sibling `[id]/[action]` handler in Next's routing, so the two never collide.
 */
export async function POST(request: NextRequest, context: { params: Promise<{ action: string }> }) {
  const { action } = await context.params;
  if (!ACTIONS.has(action)) {
    return NextResponse.json({ detail: `Bulk '${action}' is not available.` }, { status: 404 });
  }
  return forwardWrite(request, `/api/applications/bulk/${action}`, "POST");
}
