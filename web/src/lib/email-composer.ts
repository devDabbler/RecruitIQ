/**
 * Rules for the email composer (ATS Phase E), kept pure so they are tested
 * without rendering. The server refuses the same things; this only decides
 * what the buttons say.
 */
const PLACEHOLDER = /\{\{\s*([A-Za-z_]+)\s*\}\}/g;

function placeholdersIn(text: string): string[] {
  return Array.from(text.matchAll(PLACEHOLDER), (match) => match[1]);
}

export function remainingPlaceholders(...texts: string[]): string[] {
  return [...new Set(texts.flatMap(placeholdersIn))];
}

export function unknownPlaceholders(text: string, allowed: readonly string[]): string[] {
  return [...new Set(placeholdersIn(text).filter((name) => !allowed.includes(name)))];
}

export function composeClipboardText(subject: string, body: string): string {
  return `Subject: ${subject.trim()}\n\n${body.trim()}\n`;
}

export function sendState({
  canSend,
  transportConfigured,
  remaining,
}: {
  canSend: boolean;
  transportConfigured: boolean;
  remaining: string[];
}): { allowed: boolean; reason: string | null } {
  if (!canSend) {
    return { allowed: false, reason: "Your account can preview email but not send it." };
  }
  if (remaining.length > 0) {
    return {
      allowed: false,
      reason: `Fill in ${remaining.map((name) => `{{${name}}}`).join(", ")} first.`,
    };
  }
  if (!transportConfigured) {
    return {
      allowed: false,
      reason: "No mail server is configured. Copy the text and send it from your own inbox.",
    };
  }
  return { allowed: true, reason: null };
}
