import type { NextRequest } from "next/server";

import { badRequest, forwardWrite, TEMPLATE_KEY } from "@/lib/forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Edit one email template (ATS Phase E). */
export async function PUT(request: NextRequest, context: { params: Promise<{ key: string }> }) {
  const { key } = await context.params;
  if (!TEMPLATE_KEY.test(key)) return badRequest("That is not a valid template.");
  return forwardWrite(request, `/api/email-templates/${key}`, "PUT");
}
