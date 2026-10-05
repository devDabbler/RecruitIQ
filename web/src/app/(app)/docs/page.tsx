import { ChevronRight, FileJson } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import committedSpec from "@/lib/openapi.json";
import {
  buildGroups,
  inlineCode,
  paragraphs,
  type Endpoint,
  type Field,
  type OpenApiSpec,
} from "@/lib/api-reference";
import { cn } from "@/lib/utils";

export const metadata = { title: "API reference · RecruitIQ" };

const groups = buildGroups(committedSpec as unknown as OpenApiSpec);
const endpointCount = groups.reduce((n, group) => n + group.endpoints.length, 0);

const METHOD_STYLES: Record<string, string> = {
  get: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  post: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  put: "bg-amber-50 text-amber-700 ring-amber-200",
  patch: "bg-amber-50 text-amber-700 ring-amber-200",
  delete: "bg-rose-50 text-rose-700 ring-rose-200",
};

function Prose({ text }: { text: string }) {
  return (
    <>
      {inlineCode(text).map((part, i) =>
        part.code ? (
          <code
            key={i}
            className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.8em] text-slate-800"
          >
            {part.text}
          </code>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </>
  );
}

function MethodBadge({ method }: { method: string }) {
  return (
    <span
      className={cn(
        "inline-flex w-16 shrink-0 justify-center rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold uppercase ring-1 ring-inset",
        METHOD_STYLES[method] ?? "bg-slate-50 text-slate-700 ring-slate-200",
      )}
    >
      {method}
    </span>
  );
}

function FieldTable({ fields, showLocation = false }: { fields: Field[]; showLocation?: boolean }) {
  return (
    <div className="overflow-x-auto rounded-md border border-slate-200">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">Name</th>
            {showLocation ? <th className="px-3 py-2 font-medium">In</th> : null}
            <th className="px-3 py-2 font-medium">Type</th>
            <th className="px-3 py-2 font-medium">Description</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {fields.map((field) => (
            <tr key={`${field.location ?? ""}${field.name}`} className="align-top">
              <td className="px-3 py-2 font-mono whitespace-nowrap text-slate-900">
                {field.name}
                {field.required ? <span className="ml-1 font-sans text-rose-600">*</span> : null}
              </td>
              {showLocation ? <td className="px-3 py-2 text-slate-500">{field.location}</td> : null}
              <td className="px-3 py-2 font-mono text-slate-600">{field.type}</td>
              <td className="px-3 py-2 text-slate-600">
                <Prose text={field.description} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
      {children}
    </h4>
  );
}

function EndpointCard({ endpoint }: { endpoint: Endpoint }) {
  const description = paragraphs(endpoint.description);
  return (
    <details
      id={endpoint.id}
      className="group scroll-mt-20 border-b border-slate-200 last:border-b-0"
    >
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 hover:bg-slate-50 [&::-webkit-details-marker]:hidden">
        <MethodBadge method={endpoint.method} />
        <span className="min-w-0 flex-1">
          <span className="block font-mono text-sm break-all text-slate-900">{endpoint.path}</span>
          <span className="block text-xs text-slate-500">{endpoint.summary}</span>
        </span>
        <ChevronRight className="size-4 shrink-0 text-slate-400 transition-transform group-open:rotate-90" />
      </summary>

      <div className="space-y-5 border-t border-slate-100 bg-slate-50/50 px-4 py-4 text-sm">
        {description.length ? (
          <div className="space-y-2 text-slate-700">
            {description.map((paragraph, i) => (
              <p key={i}>
                <Prose text={paragraph} />
              </p>
            ))}
          </div>
        ) : null}

        {endpoint.parameters.length ? (
          <div>
            <SectionLabel>Parameters</SectionLabel>
            <FieldTable fields={endpoint.parameters} showLocation />
          </div>
        ) : null}

        {endpoint.body ? (
          <div>
            <SectionLabel>Request body</SectionLabel>
            <p className="mb-2 text-xs text-slate-500">
              <span className="font-mono text-slate-700">{endpoint.body.type}</span> as{" "}
              <span className="font-mono">{endpoint.body.contentType}</span>
            </p>
            {endpoint.body.fields.length ? <FieldTable fields={endpoint.body.fields} /> : null}
          </div>
        ) : null}

        <div>
          <SectionLabel>Responses</SectionLabel>
          <ul className="space-y-3">
            {endpoint.responses.map((response) => (
              <li key={response.status}>
                <p className="mb-2 text-xs text-slate-600">
                  <span
                    className={cn(
                      "mr-2 font-mono font-semibold",
                      response.status.startsWith("2") ? "text-emerald-700" : "text-slate-500",
                    )}
                  >
                    {response.status}
                  </span>
                  {response.description}
                  {response.type ? (
                    <span className="ml-2 font-mono text-slate-500">{response.type}</span>
                  ) : null}
                </p>
                {response.fields.length ? <FieldTable fields={response.fields} /> : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}

/**
 * The API reference, rendered from the committed OpenAPI schema.
 *
 * Built at render time from a file, not fetched: the backend is loopback-only
 * in production, so its own /docs never reaches a visitor. Native <details>
 * keeps the page server-only, with no client JavaScript for 125 endpoints.
 */
export default function ApiDocsPage() {
  return (
    <>
      <PageHeader
        title="API reference"
        description={`Every endpoint behind RecruitIQ: ${endpointCount} operations in ${groups.length} groups, generated from the backend's OpenAPI schema. CI fails any change that lets this schema drift from the code.`}
        actions={
          <a
            href="/openapi.json"
            download
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <FileJson className="size-4" />
            openapi.json
          </a>
        }
      />

      <div className="mb-8 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
        <p>
          The backend is a FastAPI service. Requests carry a bearer token from{" "}
          <code className="font-mono text-slate-800">POST /auth/login</code> or{" "}
          <code className="font-mono text-slate-800">POST /auth/demo</code>, and the demo token is
          read-only. On this hosted demo the API is reached through the web app rather than
          directly, so this page is a reference, not a console. Fields marked{" "}
          <span className="text-rose-600">*</span> are required.
        </p>
        <nav aria-label="API groups" className="mt-4 flex flex-wrap gap-2">
          {groups.map((group) => (
            <a
              key={group.tag}
              href={`#group-${group.tag}`}
              className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:border-indigo-300 hover:text-indigo-700"
            >
              {group.label} <span className="text-slate-400">{group.endpoints.length}</span>
            </a>
          ))}
        </nav>
      </div>

      <div className="space-y-8">
        {groups.map((group) => (
          <section key={group.tag} id={`group-${group.tag}`} className="scroll-mt-20">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">{group.label}</h2>
            <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
              {group.endpoints.map((endpoint) => (
                <EndpointCard key={endpoint.id} endpoint={endpoint} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
