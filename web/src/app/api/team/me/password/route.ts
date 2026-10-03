import type { NextRequest } from "next/server";

import { forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Change your own password. */
export async function PUT(request: NextRequest) {
  return forwardWrite(request, "/api/team/me/password", "PUT");
}
