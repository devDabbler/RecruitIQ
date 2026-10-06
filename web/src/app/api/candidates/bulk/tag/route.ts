import type { NextRequest } from "next/server";

import { forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Tag many candidates at once (Track 2 Phase 5). A static `bulk` segment beats
 * the sibling `[id]` routes in Next's routing, so the two never collide.
 */
export async function POST(request: NextRequest) {
  return forwardWrite(request, "/api/candidates/bulk/tag", "POST");
}
