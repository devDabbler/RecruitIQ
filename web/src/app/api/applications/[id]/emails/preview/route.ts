import type { NextRequest } from "next/server";

import { badRequest, forwardRead, NUMERIC_ID, TEMPLATE_KEY } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** A template filled in for one application, for the composer (ATS Phase E). */
export async function GET(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!NUMERIC_ID.test(id)) return badRequest("That is not a valid application id.");
  const key = request.nextUrl.searchParams.get("template_key") ?? "";
  if (!TEMPLATE_KEY.test(key)) return badRequest("That is not a valid template.");
  return forwardRead(`/api/applications/${id}/emails/preview?template_key=${key}`);
}
