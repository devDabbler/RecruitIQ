import { describe, expect, it } from "vitest";

import {
  GENERIC_FAILURE_MESSAGE,
  TIMED_OUT_MESSAGE,
  TOO_MANY_REQUESTS_MESSAGE,
  UNAVAILABLE_MESSAGE,
  messageForFailedResponse,
  messageForThrownError,
} from "./chat-errors";

const NGINX_429 =
  "<html>\r\n<head><title>429 Too Many Requests</title></head>\r\n<body>\r\n<center><h1>429 Too Many Requests</h1></center>\r\n<hr><center>nginx</center>\r\n</body>\r\n</html>";

const PYDANTIC_422 = JSON.stringify({
  detail: [
    {
      type: "string_type",
      loc: ["body", "conversation_history", 0, "content"],
      msg: "Input should be a valid string",
      input: 42,
    },
  ],
});

describe("messageForFailedResponse", () => {
  it("turns nginx's HTML rate-limit page into a sentence", () => {
    expect(messageForFailedResponse(429, NGINX_429)).toBe(TOO_MANY_REQUESTS_MESSAGE);
  });

  it("never shows HTML, whatever the status", () => {
    expect(messageForFailedResponse(500, NGINX_429)).toBe(GENERIC_FAILURE_MESSAGE);
    expect(messageForFailedResponse(503, "<html>bad gateway</html>")).toBe(UNAVAILABLE_MESSAGE);
  });

  it("never shows pydantic's validation dump", () => {
    expect(messageForFailedResponse(422, PYDANTIC_422)).toBe(GENERIC_FAILURE_MESSAGE);
  });

  it("passes a short plain detail from our own backend through", () => {
    const body = JSON.stringify({ detail: "The assistant service is not reachable right now." });
    expect(messageForFailedResponse(503, body)).toBe(
      "The assistant service is not reachable right now.",
    );
  });

  it("treats a long detail as a dump, not a message", () => {
    const body = JSON.stringify({ detail: "Traceback (most recent call last):\n".repeat(20) });
    expect(messageForFailedResponse(500, body)).toBe(GENERIC_FAILURE_MESSAGE);
  });

  it("maps gateway timeouts to the timeout line", () => {
    expect(messageForFailedResponse(504, "")).toBe(TIMED_OUT_MESSAGE);
  });

  it("maps an empty body by status", () => {
    expect(messageForFailedResponse(502, "")).toBe(UNAVAILABLE_MESSAGE);
    expect(messageForFailedResponse(500, "")).toBe(GENERIC_FAILURE_MESSAGE);
  });
});

describe("messageForThrownError", () => {
  it("reads an aborted fetch as a timeout", () => {
    const abort = new Error("The operation was aborted.");
    abort.name = "AbortError";
    expect(messageForThrownError(abort)).toBe(TIMED_OUT_MESSAGE);
  });

  it("reads anything else as the service being unreachable", () => {
    expect(messageForThrownError(new TypeError("Failed to fetch"))).toBe(UNAVAILABLE_MESSAGE);
    expect(messageForThrownError("weird")).toBe(UNAVAILABLE_MESSAGE);
  });
});
