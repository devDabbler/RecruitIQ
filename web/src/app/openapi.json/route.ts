import committedSpec from "@/lib/openapi.json";

/** The raw schema behind /docs, for anyone who wants to generate a client. */
export function GET() {
  return Response.json(committedSpec, {
    headers: { "Cache-Control": "public, max-age=3600" },
  });
}
