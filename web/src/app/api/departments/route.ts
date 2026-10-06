import type { NextRequest } from "next/server";

import { forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Add a department (Track 2 Phase 3, admin only; the API decides). */
export async function POST(request: NextRequest) {
  return forwardWrite(request, "/api/departments", "POST");
}
