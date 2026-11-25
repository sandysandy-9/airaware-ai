import type { AIChatMessage } from "./types";

export const MAX_CHAT_TURNS = 10;
export const MAX_CHAT_MESSAGE_CHARS = 1000;
/** Keep outbound history strictly below backend MAX_AGGREGATE_HISTORY_CHARS (2500) with headroom. */
export const SAFE_AGGREGATE_HISTORY_CHARS = 2200;

export interface OutboundChatTurn {
  role: "user" | "assistant";
  content: string;
  attestation?: string;
}

/**
 * Build a backend-compliant chat_history payload:
 * - Excludes UI-only greeting/error bubbles.
 * - Uses verified backend history_summary + attestation when present.
 * - Skips complete turns that exceed per-turn limits rather than truncating mid-sentence.
 * - Drops oldest complete turns first until both turn count (<= 10) and aggregate chars (<= 2200) fit.
 */
export function buildOutboundChatHistory(
  messages: AIChatMessage[],
  maxTurns: number = MAX_CHAT_TURNS,
  maxAggregateChars: number = SAFE_AGGREGATE_HISTORY_CHARS
): OutboundChatTurn[] {
  const candidates: OutboundChatTurn[] = [];
  for (const m of messages) {
    if (m.isLocalOnly) continue;
    const text = (m.historyContent ?? m.content).trim();
    if (!text || text.length > MAX_CHAT_MESSAGE_CHARS) {
      continue;
    }
    const turn: OutboundChatTurn = { role: m.role, content: text };
    if (m.role === "assistant" && m.attestation) {
      turn.attestation = m.attestation;
    }
    candidates.push(turn);
  }

  const trimmed = candidates.slice(-maxTurns);
  let totalChars = trimmed.reduce((acc, t) => acc + t.content.length, 0);
  while (trimmed.length > 0 && totalChars > maxAggregateChars) {
    const removed = trimmed.shift();
    if (removed) {
      totalChars -= removed.content.length;
    }
  }
  return trimmed;
}

export function classifyApiErrorMessage(err: unknown): {
  kind: "validation" | "rate_limit" | "server" | "network";
  message: string;
} {
  if (err && typeof err === "object" && "status" in err && typeof (err as { status: unknown }).status === "number") {
    const status = (err as { status: number }).status;
    const msg = err instanceof Error ? err.message : `Request failed (${status})`;
    if (status === 422) {
      return {
        kind: "validation",
        message: `Input or request validation error (HTTP 422): ${msg}`,
      };
    }
    if (status === 429) {
      return {
        kind: "rate_limit",
        message: `Rate limit reached (HTTP 429): ${msg}. Please wait briefly before retrying.`,
      };
    }
    return {
      kind: "server",
      message: `Backend service returned HTTP ${status}: ${msg}. Verified dashboard readings remain accessible above.`,
    };
  }
  return {
    kind: "network",
    message:
      "Unable to reach the AirAware backend server due to a network or connectivity error. Verified dashboard readings remain accessible above.",
  };
}
