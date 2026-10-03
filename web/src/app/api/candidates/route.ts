import type { NextRequest } from "next/server";

import { forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Add a candidate by hand (ATS Phase C). A job_id starts their pipeline too. */
export async function POST(request: NextRequest) {
  return forwardWrite(request, "/api/candidates/", "POST");
}
