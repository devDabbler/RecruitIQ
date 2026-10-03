import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, USER_ID } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Change someone's role. */
export async function PUT(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!USER_ID.test(id)) return badRequest("That is not a valid user id.");
  return forwardWrite(request, `/api/team/users/${id}/role`, "PUT");
}
