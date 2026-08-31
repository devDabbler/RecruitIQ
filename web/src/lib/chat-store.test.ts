import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MAX_CONVERSATIONS,
  type StoredConversation,
  conversationTitle,
  deleteConversation,
  loadConversations,
  newConversationId,
  saveConversation,
} from "./chat-store";

/** Minimal in-memory Storage; the vitest environment is node, not jsdom. */
function fakeStorage(): Storage {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
    clear: () => data.clear(),
    key: (i: number) => [...data.keys()][i] ?? null,
    get length() {
      return data.size;
    },
  };
}

function convo(id: string, updatedAt: number, content = "find python engineers"): StoredConversation {
  return {
    id,
    title: content,
    updatedAt,
    turns: [
      { role: "user", content },
      { role: "assistant", content: "Here are the results." },
    ],
    context: {},
  };
}

beforeEach(() => {
  vi.stubGlobal("localStorage", fakeStorage());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("save and load", () => {
  it("round-trips a conversation", () => {
    const c = convo("a", 1);
    saveConversation(c);
    expect(loadConversations()).toEqual([c]);
  });

  it("returns newest first regardless of save order", () => {
    saveConversation(convo("old", 1));
    saveConversation(convo("new", 3));
    saveConversation(convo("mid", 2));
    expect(loadConversations().map((c) => c.id)).toEqual(["new", "mid", "old"]);
  });

  it("updates in place instead of duplicating", () => {
    saveConversation(convo("a", 1));
    const updated = { ...convo("a", 2), title: "changed" };
    saveConversation(updated);
    const all = loadConversations();
    expect(all).toHaveLength(1);
    expect(all[0].title).toBe("changed");
  });

  it("does not save an empty conversation", () => {
    saveConversation({ id: "empty", title: "", updatedAt: 1, turns: [], context: {} });
    expect(loadConversations()).toEqual([]);
  });

  it("caps history at MAX_CONVERSATIONS, dropping the oldest", () => {
    for (let i = 0; i < MAX_CONVERSATIONS + 5; i++) {
      saveConversation(convo(`c${i}`, i));
    }
    const all = loadConversations();
    expect(all).toHaveLength(MAX_CONVERSATIONS);
    expect(all[0].id).toBe(`c${MAX_CONVERSATIONS + 4}`);
  });
});

describe("deleteConversation", () => {
  it("removes only the given conversation", () => {
    saveConversation(convo("keep", 1));
    saveConversation(convo("drop", 2));
    deleteConversation("drop");
    expect(loadConversations().map((c) => c.id)).toEqual(["keep"]);
  });
});

describe("robustness", () => {
  it("reads corrupted storage as no history", () => {
    localStorage.setItem("recruitiq.assistant.conversations.v1", "{not json");
    expect(loadConversations()).toEqual([]);
  });

  it("reads a non-array payload as no history", () => {
    localStorage.setItem("recruitiq.assistant.conversations.v1", '{"id":"x"}');
    expect(loadConversations()).toEqual([]);
  });

  it("survives a missing localStorage entirely", () => {
    vi.stubGlobal("localStorage", undefined);
    expect(loadConversations()).toEqual([]);
    expect(() => saveConversation(convo("a", 1))).not.toThrow();
  });

  it("survives a storage that throws on write (private mode)", () => {
    const throwing = fakeStorage();
    throwing.setItem = () => {
      throw new Error("QuotaExceededError");
    };
    vi.stubGlobal("localStorage", throwing);
    expect(() => saveConversation(convo("a", 1))).not.toThrow();
  });
});

describe("conversationTitle", () => {
  it("uses the first user message", () => {
    expect(
      conversationTitle([
        { role: "assistant", content: "hi" },
        { role: "user", content: "  who is in Seattle?  " },
      ]),
    ).toBe("who is in Seattle?");
  });

  it("truncates long messages", () => {
    const long = "x".repeat(200);
    const title = conversationTitle([{ role: "user", content: long }]);
    expect(title.length).toBeLessThanOrEqual(64);
    expect(title.endsWith("…")).toBe(true);
  });

  it("falls back when there is no user turn", () => {
    expect(conversationTitle([])).toBe("New conversation");
  });
});

describe("newConversationId", () => {
  it("produces unique ids", () => {
    expect(newConversationId()).not.toBe(newConversationId());
  });
});
