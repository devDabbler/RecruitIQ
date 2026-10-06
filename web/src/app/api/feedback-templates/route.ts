import type { NextRequest } from "next/server";

import { forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Create a feedback template, global or for one job (Track 2 Phase 4). */
export async function POST(request: NextRequest) {
  return forwardWrite(request, "/api/feedback-templates", "POST");
}
