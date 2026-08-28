import { describe, expect, it } from "vitest";

import { readSse, type SseEvent } from "./sse";

/** A stream that emits exactly the given chunks, so boundaries are controlled. */
function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

function bytesOf(...chunks: string[]): Uint8Array {
  return new TextEncoder().encode(chunks.join(""));
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<SseEvent[]> {
  const events: SseEvent[] = [];
  for await (const event of readSse(stream)) events.push(event);
  return events;
}

describe("readSse", () => {
  it("reads a full tool-call turn in order", async () => {
    const events = await collect(
      streamOf(
        'event: tool_start\ndata: {"tool":"search_candidates"}\n\n',
        'event: tool_end\ndata: {"tool":"search_candidates","count":12}\n\n',
        'event: message\ndata: {"response":"I found 12 candidates."}\n\n',
      ),
    );

    expect(events.map((e) => e.name)).toEqual(["tool_start", "tool_end", "message"]);
    expect(events[1].data).toEqual({ tool: "search_candidates", count: 12 });
    expect(events[2].data).toEqual({ response: "I found 12 candidates." });
  });

  it("reassembles an event split across chunk boundaries", async () => {
    // The realistic failure: TCP does not respect our framing, so an event can
    // arrive in pieces. Splitting mid-`data:` line must not drop or duplicate.
    const events = await collect(
      streamOf('event: tool_st', 'art\ndata: {"tool":"sc', 'ore_matches"}', "\n\n"),
    );

    expect(events).toEqual([{ name: "tool_start", data: { tool: "score_matches" } }]);
  });

  it("emits several events arriving in one chunk", async () => {
    const events = await collect(
      streamOf('event: a\ndata: 1\n\nevent: b\ndata: 2\n\nevent: c\ndata: 3\n\n'),
    );
    expect(events).toEqual([
      { name: "a", data: 1 },
      { name: "b", data: 2 },
      { name: "c", data: 3 },
    ]);
  });

  it("survives a multi-byte character split across chunks", async () => {
    // "é" is two bytes in UTF-8. Decoding each chunk independently would yield
    // a replacement character, which is exactly what `stream: true` prevents.
    const payload = bytesOf('event: message\ndata: {"response":"café"}\n\n');
    const cut = payload.indexOf(0xc3) + 1; // between the two bytes of "é"

    const events = await collect(
      new ReadableStream({
        start(controller) {
          controller.enqueue(payload.slice(0, cut));
          controller.enqueue(payload.slice(cut));
          controller.close();
        },
      }),
    );

    expect(events).toEqual([{ name: "message", data: { response: "café" } }]);
  });

  it("defaults the event name to `message` when none is given", async () => {
    const events = await collect(streamOf('data: {"ok":true}\n\n'));
    expect(events).toEqual([{ name: "message", data: { ok: true } }]);
  });

  it("yields non-JSON data as a plain string", async () => {
    const events = await collect(streamOf("event: error\ndata: upstream timed out\n\n"));
    expect(events).toEqual([{ name: "error", data: "upstream timed out" }]);
  });

  it("joins multi-line data fields with newlines", async () => {
    const events = await collect(streamOf("event: message\ndata: line one\ndata: line two\n\n"));
    expect(events).toEqual([{ name: "message", data: "line one\nline two" }]);
  });

  it("skips comment-only and dataless events", async () => {
    // FastAPI/nginx keep-alive comments arrive as `: ping`. Yielding those as
    // events would put empty bubbles in the chat.
    const events = await collect(
      streamOf(": ping\n\n", "event: tool_start\n\n", 'event: message\ndata: "done"\n\n'),
    );
    expect(events).toEqual([{ name: "message", data: "done" }]);
  });

  it("discards a trailing partial event rather than yielding a truncated one", async () => {
    const events = await collect(
      streamOf('event: message\ndata: {"response":"complete"}\n\n', 'event: message\ndata: {"resp'),
    );
    expect(events).toEqual([{ name: "message", data: { response: "complete" } }]);
  });

  it("returns nothing for an empty stream", async () => {
    await expect(collect(streamOf())).resolves.toEqual([]);
  });
});
