/**
 * Turns the committed OpenAPI schema into the API reference page at /docs.
 *
 * The backend's own Swagger UI is unreachable in production: nginx sends every
 * public path to this app and the API listens on loopback only. So the
 * reference is built from `openapi.json` at the repo root, which CI already
 * checks against the live routes (`export_openapi.py --check`), and it can
 * never drift from the code without a red build.
 */

export interface OpenApiSchema {
  $ref?: string;
  type?: string;
  format?: string;
  title?: string;
  description?: string;
  items?: OpenApiSchema;
  anyOf?: OpenApiSchema[];
  oneOf?: OpenApiSchema[];
  allOf?: OpenApiSchema[];
  enum?: unknown[];
  const?: unknown;
  properties?: Record<string, OpenApiSchema>;
  required?: string[];
  additionalProperties?: boolean | OpenApiSchema;
}

interface MediaType {
  schema?: OpenApiSchema;
}

interface OpenApiParameter {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: OpenApiSchema;
}

interface OpenApiOperation {
  summary?: string;
  description?: string;
  operationId?: string;
  tags?: string[];
  parameters?: OpenApiParameter[];
  requestBody?: { required?: boolean; content?: Record<string, MediaType> };
  responses?: Record<string, { description?: string; content?: Record<string, MediaType> }>;
}

export interface OpenApiSpec {
  paths: Record<string, Partial<Record<string, OpenApiOperation>>>;
  components?: { schemas?: Record<string, OpenApiSchema> };
}

export interface Field {
  name: string;
  /** Where a parameter travels (path, query, header). Absent for body fields. */
  location?: string;
  type: string;
  required: boolean;
  description: string;
}

export interface Payload {
  contentType: string;
  type: string;
  fields: Field[];
}

export interface ResponseRow {
  status: string;
  description: string;
  type: string | null;
  fields: Field[];
}

export interface Endpoint {
  id: string;
  method: string;
  path: string;
  summary: string;
  description: string;
  parameters: Field[];
  body: Payload | null;
  responses: ResponseRow[];
}

export interface ApiGroup {
  tag: string;
  label: string;
  endpoints: Endpoint[];
}

export const METHODS = ["get", "post", "put", "patch", "delete", "head"] as const;

/** Routes FastAPI declared without a tag (health, root). */
export const UNTAGGED = "general";

/**
 * The product surface first, in the order the sidebar presents it, then
 * whatever is left (legacy and operational routers) alphabetically.
 */
const TAG_ORDER = [
  "auth",
  "jobs",
  "candidates",
  "pipeline",
  "interviews",
  "notes",
  "tags",
  "status-links",
  "email",
  "job-drafts",
  "reports",
  "team",
  "matching",
  "enhanced-matching",
  "resume",
  "assistant",
  "transparency",
];

/** No em or en dashes on screen, even when a docstring has one. */
export function plainText(text: string): string {
  return text.replace(/\s*[—–]\s*/g, " - ");
}

/**
 * Docstrings are hard-wrapped at 79 columns. Rewrap them: blank lines split
 * paragraphs, single newlines are just line length.
 */
export function paragraphs(text: string | undefined): string[] {
  if (!text) return [];
  return plainText(text)
    .split(/\n\s*\n/)
    .map((block) => block.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

/** Splits `inline code` out of a sentence so it can render monospaced. */
export function inlineCode(text: string): { code: boolean; text: string }[] {
  return text
    .split("`")
    .map((part, i) => ({ code: i % 2 === 1, text: part }))
    .filter((part) => part.text !== "");
}

export function refName(ref: string): string {
  return ref.slice(ref.lastIndexOf("/") + 1);
}

const SHOWN_FORMATS = new Set(["date", "date-time", "uuid", "binary", "email", "uri"]);

/** A one-line, developer-readable type: `string | null`, `JobOut[]`. */
export function typeLabel(schema: OpenApiSchema | undefined): string {
  if (!schema) return "any";
  if (schema.$ref) return refName(schema.$ref);

  const union = schema.anyOf ?? schema.oneOf;
  if (union?.length) {
    const labels = [...new Set(union.map(typeLabel))];
    return labels.join(" | ");
  }
  if (schema.allOf?.length === 1) return typeLabel(schema.allOf[0]);
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  if (schema.enum?.length) return schema.enum.map((value) => JSON.stringify(value)).join(" | ");

  if (schema.type === "array") {
    const inner = typeLabel(schema.items);
    return inner.includes(" | ") ? `(${inner})[]` : `${inner}[]`;
  }
  if (schema.type === "object" || schema.additionalProperties) {
    if (schema.additionalProperties && typeof schema.additionalProperties === "object") {
      return `map of ${typeLabel(schema.additionalProperties)}`;
    }
    return "object";
  }
  if (schema.type) {
    return schema.format && SHOWN_FORMATS.has(schema.format)
      ? `${schema.type} (${schema.format})`
      : schema.type;
  }
  return "any";
}

function resolve(schema: OpenApiSchema | undefined, spec: OpenApiSpec): OpenApiSchema | undefined {
  let current = schema;
  // allOf-of-one is how Pydantic wraps a $ref that carries a description.
  for (let hops = 0; current && hops < 5; hops++) {
    if (current.$ref) current = spec.components?.schemas?.[refName(current.$ref)];
    else if (current.allOf?.length === 1) current = current.allOf[0];
    else break;
  }
  return current;
}

/** The top-level fields of an object schema, one level deep; nested models show by name. */
export function schemaFields(schema: OpenApiSchema | undefined, spec: OpenApiSpec): Field[] {
  let target = resolve(schema, spec);
  if (target?.type === "array") target = resolve(target.items, spec);
  if (!target?.properties) return [];
  const required = new Set(target.required ?? []);
  return Object.entries(target.properties).map(([name, field]) => ({
    name,
    type: typeLabel(field),
    required: required.has(name),
    description: plainText(field.description ?? ""),
  }));
}

function firstMedia(content: Record<string, MediaType> | undefined): [string, MediaType] | null {
  if (!content) return null;
  const entries = Object.entries(content);
  return entries.length ? entries[0] : null;
}

function toEndpoint(
  method: string,
  path: string,
  op: OpenApiOperation,
  spec: OpenApiSpec,
): Endpoint {
  const parameters = (op.parameters ?? []).map((param) => ({
    name: param.name,
    location: param.in,
    type: typeLabel(param.schema),
    required: Boolean(param.required),
    description: plainText(param.description ?? param.schema?.description ?? ""),
  }));

  const bodyMedia = firstMedia(op.requestBody?.content);
  const body = bodyMedia
    ? {
        contentType: bodyMedia[0],
        type: typeLabel(bodyMedia[1].schema),
        fields: schemaFields(bodyMedia[1].schema, spec),
      }
    : null;

  const responses = Object.entries(op.responses ?? {}).map(([status, response]) => {
    const media = firstMedia(response.content);
    const schema = media?.[1].schema;
    const hasSchema = schema !== undefined && Object.keys(schema).length > 0;
    return {
      status,
      description: plainText(response.description ?? ""),
      type: hasSchema ? typeLabel(schema) : null,
      // Field tables for success bodies only: every 422 is the same
      // HTTPValidationError, and repeating it 100 times helps nobody.
      fields: status.startsWith("2") ? schemaFields(schema, spec) : [],
    };
  });

  return {
    // Keeps a trailing slash distinct: /api/jobs and /api/jobs/ are both routes.
    id: `${method}${path}`.replace(/[{}]/g, "").replace(/[^a-zA-Z0-9_]/g, "-"),
    method,
    path,
    summary: plainText(op.summary ?? op.operationId ?? path),
    description: op.description ?? "",
    parameters,
    body,
    responses,
  };
}

export function tagLabel(tag: string): string {
  const words = tag.replace(/[-_]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function tagRank(tag: string): number {
  const index = TAG_ORDER.indexOf(tag);
  return index === -1 ? TAG_ORDER.length : index;
}

/** Every operation in the spec, grouped by its first tag, product groups first. */
export function buildGroups(spec: OpenApiSpec): ApiGroup[] {
  const groups = new Map<string, Endpoint[]>();
  for (const [path, item] of Object.entries(spec.paths)) {
    for (const method of METHODS) {
      const op = item[method];
      if (!op) continue;
      const tag = op.tags?.[0] ?? UNTAGGED;
      if (!groups.has(tag)) groups.set(tag, []);
      groups.get(tag)!.push(toEndpoint(method, path, op, spec));
    }
  }
  return [...groups.entries()]
    .map(([tag, endpoints]) => ({ tag, label: tagLabel(tag), endpoints }))
    .sort((a, b) => tagRank(a.tag) - tagRank(b.tag) || a.tag.localeCompare(b.tag));
}
