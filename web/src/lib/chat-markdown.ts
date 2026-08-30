/**
 * Minimal markdown for assistant bubbles: **bold** and [label](href) links.
 *
 * The assistant is instructed to link candidates and jobs it mentions to their
 * profile pages. Only same-origin profile paths become links; any other target
 * (external URLs, hallucinated routes) renders as plain text, so a misbehaving
 * model cannot make the chat link off-site.
 */

export type ChatSegment =
  | { kind: "text"; text: string }
  | { kind: "bold"; text: string }
  | { kind: "link"; text: string; href: string };

const TOKEN = /\[([^\]\n]+)\]\(([^)\s]+)\)|\*\*([^*\n]+)\*\*/g;
const INTERNAL_HREF = /^\/(candidates|jobs)\/[A-Za-z0-9_-]+$/;

export function parseChatMarkdown(content: string): ChatSegment[] {
  const segments: ChatSegment[] = [];
  let cursor = 0;

  for (const match of content.matchAll(TOKEN)) {
    if (match.index > cursor) {
      segments.push({ kind: "text", text: content.slice(cursor, match.index) });
    }
    const [token, label, href, bold] = match;
    if (bold !== undefined) {
      segments.push({ kind: "bold", text: bold });
    } else if (INTERNAL_HREF.test(href)) {
      segments.push({ kind: "link", text: label, href });
    } else {
      segments.push({ kind: "text", text: label });
    }
    cursor = match.index + token.length;
  }

  if (cursor < content.length) {
    segments.push({ kind: "text", text: content.slice(cursor) });
  }
  return segments;
}
