import type { NextRequest } from "next/server";

import { forwardWrite } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Invite someone to the team. */
export async function POST(request: NextRequest) {
  return forwardWrite(request, "/api/team/users", "POST");
}
