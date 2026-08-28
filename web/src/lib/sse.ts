/**
 * Minimal SSE reader for a POST response.
 *
 * `EventSource` is not an option: it can only issue GETs and cannot carry the
 * conversation history, so the stream has to be read off `fetch` by hand.
 *
 * Only the two fields the backend emits are parsed — `event:` and `data:`.
 * Retry hints, ids, and comment lines are irrelevant against our own endpoint,
 * and implementing them would be code no test could justify.
 */
export interface SseEvent {
  name: string;
  data: unknown;
}

export async function* readSse(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent, void, unknown> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // `stream: true` matters: a chunk boundary can land mid-UTF-8-sequence,
      // and decoding each chunk independently would corrupt any non-ASCII
      // character that straddles it.
      buffer += decoder.decode(value, { stream: true });

      // Events are separated by a blank line. Anything after the last one is a
      // partial event and stays in the buffer.
      let split: number;
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);

        let name = "message";
        const dataLines: string[] = [];
        for (const line of raw.split("\n")) {
          if (line.startsWith("event:")) name = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
        }
        if (dataLines.length === 0) continue;

        const text = dataLines.join("\n");
        try {
          yield { name, data: JSON.parse(text) };
        } catch {
          yield { name, data: text };
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
