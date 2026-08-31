/**
 * Assistant chat history, kept in localStorage.
 *
 * The demo has no per-user server state (every visitor shares one read-only
 * database), so conversations belong to the browser, not the backend. Every
 * accessor swallows storage failures: private-mode browsers that throw on
 * write, disabled storage, or a corrupted value must degrade to "no history",
 * never break the chat itself.
 */

export interface StoredToolEvent {
  tool: string;
  state: "running" | "ok" | "failed";
  summary?: string;
}

export interface StoredTurn {
  role: "user" | "assistant";
  content: string;
  tools?: StoredToolEvent[];
  failed?: boolean;
}

export interface StoredConversation {
  id: string;
  title: string;
  updatedAt: number;
  turns: StoredTurn[];
  context: Record<string, unknown>;
}

const STORAGE_KEY = "recruitiq.assistant.conversations.v1";

/** Newest-first cap; the oldest conversation falls off, like any chat app. */
export const MAX_CONVERSATIONS = 20;

const TITLE_MAX_CHARS = 64;

function storage(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function newConversationId(): string {
  try {
    return globalThis.crypto.randomUUID();
  } catch {
    return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

/** First user message, truncated, as the list label. */
export function conversationTitle(turns: StoredTurn[]): string {
  const first = turns.find((t) => t.role === "user" && t.content.trim())?.content.trim();
  if (!first) return "New conversation";
  return first.length > TITLE_MAX_CHARS ? `${first.slice(0, TITLE_MAX_CHARS - 1)}…` : first;
}

/** All saved conversations, newest first. Corrupted storage reads as empty. */
export function loadConversations(): StoredConversation[] {
  const store = storage();
  if (!store) return [];
  try {
    const raw = store.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (c): c is StoredConversation =>
          !!c && typeof c.id === "string" && Array.isArray(c.turns) && c.turns.length > 0,
      )
      .sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

function persist(conversations: StoredConversation[]): void {
  const store = storage();
  if (!store) return;
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(conversations.slice(0, MAX_CONVERSATIONS)));
  } catch {
    // Quota or private mode: history just does not persist this time.
  }
}

/** Insert or update one conversation. Empty conversations are not saved. */
export function saveConversation(conversation: StoredConversation): void {
  if (conversation.turns.length === 0) return;
  const rest = loadConversations().filter((c) => c.id !== conversation.id);
  persist([conversation, ...rest]);
}

export function deleteConversation(id: string): void {
  persist(loadConversations().filter((c) => c.id !== id));
}
