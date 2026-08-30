"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, Bot, Check, Loader2, User, Wrench, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { parseChatMarkdown } from "@/lib/chat-markdown";
import { readSse } from "@/lib/sse";
import { cn } from "@/lib/utils";

interface ToolEvent {
  tool: string;
  state: "running" | "ok" | "failed";
  summary?: string;
}

interface Turn {
  role: "user" | "assistant";
  content: string;
  tools?: ToolEvent[];
  failed?: boolean;
}

// One suggestion per capability the assistant demos well; a random handful is
// shown per visit so repeat visitors see the breadth, not the same three chips.
const SUGGESTION_POOL = [
  "Who are the strongest candidates for the Senior Backend Engineer role?",
  "Find Python engineers in Seattle",
  "How many candidates are in the interviewing stage?",
  "Which skills show up most often across the pipeline?",
  "What is the market salary for a Data Engineer in Austin?",
  "Show me machine learning candidates and where they are located",
  "Why is our top candidate a good fit for the NLP Engineer role?",
  "Summarize the pipeline for me",
];

const SUGGESTION_COUNT = 4;

function sampleSuggestions(): string[] {
  const pool = [...SUGGESTION_POOL];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, SUGGESTION_COUNT);
}

/**
 * The assistant, with its tool calls narrated as they happen.
 *
 * The turn is three model calls plus database work and only the last produces
 * prose, so the interesting thing to stream is the *tool activity* — watching
 * `search_candidates → 12 results → scoring` is what shows this is querying a
 * real ATS rather than improvising (spec §5).
 */
export function AssistantChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [context, setContext] = useState<Record<string, unknown>>({});
  // Sampled after mount: Math.random() during render would make the server and
  // client HTML disagree and trip hydration.
  const [suggestions, setSuggestions] = useState<string[]>(() =>
    SUGGESTION_POOL.slice(0, SUGGESTION_COUNT),
  );
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSuggestions(sampleSuggestions());
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function send(message: string) {
    const text = message.trim();
    if (!text || busy) return;

    // The history sent upstream is the state *before* this turn — appending
    // first and then reading state would include the question twice.
    const history = turns.map((turn) => ({ role: turn.role, content: turn.content }));

    setDraft("");
    setBusy(true);
    setTurns((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", tools: [] },
    ]);

    /** Rewrite the in-flight assistant turn, which is always the last one. */
    function patch(update: (turn: Turn) => Turn) {
      setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? update(t) : t)));
    }

    try {
      const response = await fetch("/api/assistant/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_history: history,
          conversation_context: context,
        }),
      });

      if (!response.ok || !response.body) {
        const detail = await response.text().catch(() => "");
        throw new Error(detail || `Assistant request failed (${response.status})`);
      }

      for await (const event of readSse(response.body)) {
        const data = event.data as Record<string, unknown>;

        if (event.name === "tool_start") {
          patch((turn) => ({
            ...turn,
            tools: [...(turn.tools ?? []), { tool: String(data.tool), state: "running" }],
          }));
        } else if (event.name === "tool_end") {
          patch((turn) => ({
            ...turn,
            tools: (turn.tools ?? []).map((tool, i, all) =>
              // Mark the most recent matching call, not the first: the loop can
              // invoke the same tool twice in one turn.
              i === all.findLastIndex((t) => t.tool === data.tool && t.state === "running")
                ? {
                    ...tool,
                    state: data.ok === false ? "failed" : "ok",
                    summary: data.summary ? String(data.summary) : undefined,
                  }
                : tool,
            ),
          }));
        } else if (event.name === "message") {
          patch((turn) => ({ ...turn, content: String(data.response ?? "") }));
          if (data.conversation_context && typeof data.conversation_context === "object") {
            setContext(data.conversation_context as Record<string, unknown>);
          }
        } else if (event.name === "error") {
          patch((turn) => ({
            ...turn,
            content: String(data.detail ?? "The assistant failed."),
            failed: true,
          }));
        }
      }
    } catch (error) {
      patch((turn) => ({ ...turn, content: (error as Error).message, failed: true }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-16rem)] min-h-[28rem] flex-col rounded-xl border border-slate-200 bg-white">
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {turns.length === 0 ? (
          <div className="space-y-4">
            <p className="text-sm text-slate-500">
              Ask about the candidates and roles in the database. The assistant answers by calling
              real API tools, and you will see each one as it runs.
            </p>
            <div className="flex flex-col items-start gap-2">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => send(suggestion)}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-left text-sm text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          turns.map((turn, index) => <Bubble key={index} turn={turn} busy={busy} />)
        )}
        <div ref={bottom} />
      </div>

      <form
        className="flex items-end gap-2 border-t border-slate-200 p-4"
        onSubmit={(e) => {
          e.preventDefault();
          void send(draft);
        }}
      >
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            // Enter sends, Shift+Enter breaks the line — the convention every
            // chat UI has trained people to expect.
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send(draft);
            }
          }}
          rows={1}
          placeholder="Ask about candidates, roles, or the pipeline…"
          aria-label="Message the assistant"
          className="max-h-40 min-h-11 resize-none"
        />
        <Button type="submit" size="icon" disabled={busy || !draft.trim()} aria-label="Send">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
        </Button>
      </form>
    </div>
  );
}

function Bubble({ turn, busy }: { turn: Turn; busy: boolean }) {
  const isUser = turn.role === "user";
  return (
    <div className={cn("flex gap-3", isUser && "justify-end")}>
      {!isUser ? (
        <span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-indigo-600 text-white">
          <Bot className="h-4 w-4" aria-hidden />
        </span>
      ) : null}

      <div className={cn("max-w-2xl min-w-0", isUser && "order-first")}>
        {turn.tools?.length ? (
          <ul className="mb-2 space-y-1">
            {turn.tools.map((tool, i) => (
              <li
                key={`${tool.tool}-${i}`}
                className="flex items-center gap-2 text-xs text-slate-500"
              >
                {tool.state === "running" ? (
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-blue-500" />
                ) : tool.state === "ok" ? (
                  <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                ) : (
                  <X className="h-3.5 w-3.5 shrink-0 text-rose-500" />
                )}
                <Wrench className="h-3 w-3 shrink-0 text-slate-300" aria-hidden />
                <code className="font-mono text-slate-600">{tool.tool}</code>
                {tool.summary ? <span className="truncate">· {tool.summary}</span> : null}
              </li>
            ))}
          </ul>
        ) : null}

        {turn.content ? (
          <div
            className={cn(
              "rounded-2xl px-4 py-2.5 text-sm whitespace-pre-line",
              isUser
                ? "bg-indigo-600 text-white"
                : turn.failed
                  ? "border border-rose-200 bg-rose-50 text-rose-800"
                  : "bg-slate-100 text-slate-800",
            )}
          >
            {isUser ? turn.content : <AssistantText content={turn.content} />}
          </div>
        ) : busy && !isUser ? (
          <p className="text-sm text-slate-400">Thinking…</p>
        ) : null}
      </div>

      {isUser ? (
        <span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-slate-200 text-slate-600">
          <User className="h-4 w-4" aria-hidden />
        </span>
      ) : null}
    </div>
  );
}

/** Assistant prose with candidate/job profile links and bold rendered. */
function AssistantText({ content }: { content: string }) {
  return (
    <>
      {parseChatMarkdown(content).map((segment, i) => {
        if (segment.kind === "link") {
          return (
            <Link
              key={i}
              href={segment.href}
              className="font-medium text-indigo-700 underline underline-offset-2 hover:text-indigo-900"
            >
              {segment.text}
            </Link>
          );
        }
        if (segment.kind === "bold") {
          return (
            <strong key={i} className="font-semibold">
              {segment.text}
            </strong>
          );
        }
        return <span key={i}>{segment.text}</span>;
      })}
    </>
  );
}
