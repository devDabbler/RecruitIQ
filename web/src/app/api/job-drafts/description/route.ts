import type { NextRequest } from "next/server";

import { forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Draft a job overview and qualifications with AI (ATS Phase E). Saves nothing. */
export async function POST(request: NextRequest) {
  return forwardWrite(request, "/api/job-drafts/description", "POST");
}
