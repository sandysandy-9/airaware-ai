import type { AIChatMessage } from "./types";

export const MAX_CHAT_TURNS = 10;
export const MAX_CHAT_MESSAGE_CHARS = 1000;
/** Keep outbound history strictly below backend MAX_AGGREGATE_HISTORY_CHARS (2500) with headroom. */
export const SAFE_AGGREGATE_HISTORY_CHARS = 2200;

export interface ChatComparisonCityCandidate {
  id: string;
  name: string;
  city?: string;
}

export interface ChatCoordinateLocation {
  city?: string;
  latitude?: number;
  longitude?: number;
}

const NON_CITY_OPERAND_PATTERN =
  "(?:pm\\s*2\\.?5|pm\\s*10|no2|so2|co|o3|nh3|ozone|aqi|air\\s+quality|index|humidity|temperature|temp|wind|weather|morning|evening|afternoon|night|today'?s?|yesterday'?s?|tomorrow'?s?|indoor|outdoor|levels?|concentrations?)";

const NON_CITY_PAIR_REGEX = new RegExp(
  `\\b(?:between\\s+${NON_CITY_OPERAND_PATTERN}\\s+and\\s+${NON_CITY_OPERAND_PATTERN}|${NON_CITY_OPERAND_PATTERN}\\s+(?:vs\\.?|versus|compared\\s+to|compared\\s+with)\\s+${NON_CITY_OPERAND_PATTERN})\\b`,
  "i"
);

const CITY_COMPARISON_INTENT_REGEX =
  /\b(compar\w*|versus|vs\.?|between|difference|better|worse|cleaner|dirtier|safer|higher|lower|more\s+polluted|less\s+polluted|which\s+(?:city|location|place|one))\b/i;

const EXPLICIT_CURRENT_LOCATION_REF_REGEX =
  /\b(this\s+location|current\s+location|my\s+location|current\s+city)\b/i;

/**
 * Extract 2..6 comparison locations when a user explicitly asks to compare air quality across cities,
 * enabling server-verified multi-city context in /api/v1/ai/chat.
 *
 * Does not auto-add the active location when only one city is mentioned, and ignores
 * pollutant, time-of-day, or meteorological comparisons scoped to a single city.
 */
export function extractComparisonTargets(
  message: string,
  currentLocation: ChatCoordinateLocation,
  knownCities: ChatComparisonCityCandidate[]
): Array<{ city?: string; latitude?: number; longitude?: number }> | undefined {
  const normalizedMsg = message.trim().toLowerCase();
  if (!normalizedMsg) return undefined;

  if (!CITY_COMPARISON_INTENT_REGEX.test(normalizedMsg)) {
    return undefined;
  }

  const matchedCities: Array<{ city: string }> = [];
  const seenCities = new Set<string>();

  const pushCity = (name: string) => {
    const key = name.trim().toLowerCase();
    if (!key || seenCities.has(key) || matchedCities.length >= 6) return;
    seenCities.add(key);
    matchedCities.push({ city: name.trim() });
  };

  for (const c of knownCities) {
    const candidates = [c.name.toLowerCase(), c.id.toLowerCase()];
    if (c.city) candidates.push(c.city.toLowerCase());
    // Support common Delhi alias cleanly without duplicating New Delhi
    if (c.id === "delhi") candidates.push("delhi");
    const matched = candidates.some((tok) => {
      const escaped = tok.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return new RegExp(`\\b${escaped}\\b`, "i").test(normalizedMsg);
    });
    if (matched) {
      pushCity(c.name);
    }
  }

  // Require at least two explicit cities; never auto-add currentLocation for single-city queries.
  if (matchedCities.length < 2) {
    return undefined;
  }

  // Guard against questions comparing two non-city variables (e.g. "PM2.5 vs PM10 in Delhi and Mumbai")
  if (NON_CITY_PAIR_REGEX.test(normalizedMsg)) {
    const cityTokenGroup = knownCities
      .flatMap((c) => {
        const list = [c.name.toLowerCase(), c.id.toLowerCase()];
        if (c.city) list.push(c.city.toLowerCase());
        if (c.id === "delhi") list.push("delhi");
        return list;
      })
      .map((tok) => tok.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
      .join("|");
    const cityComparisonCueRegex = new RegExp(
      `(?:compar\\w+\\s+(?:with|to)\\s+(?:${cityTokenGroup})\\b|\\bbetween\\s+(?:${cityTokenGroup})\\b|\\b(?:${cityTokenGroup})\\b\\s+(?:vs\\.?|versus)\\s+\\b(?:${cityTokenGroup})\\b|\\bwhich\\s+(?:city|location|place|one)\\b)`,
      "i"
    );
    if (!cityComparisonCueRegex.test(normalizedMsg)) {
      return undefined;
    }
  }

  const targets: Array<{ city?: string; latitude?: number; longitude?: number }> = [];
  if (EXPLICIT_CURRENT_LOCATION_REF_REGEX.test(normalizedMsg)) {
    if (
      typeof currentLocation.latitude === "number" &&
      typeof currentLocation.longitude === "number" &&
      (!currentLocation.city ||
        currentLocation.city.startsWith("Custom Coordinates") ||
        currentLocation.city.startsWith("Near "))
    ) {
      targets.push({
        latitude: currentLocation.latitude,
        longitude: currentLocation.longitude,
      });
    } else if (currentLocation.city) {
      const curKey = currentLocation.city.trim().toLowerCase();
      if (curKey && !seenCities.has(curKey)) {
        targets.push({ city: currentLocation.city.trim() });
      }
    }
  }

  for (const c of matchedCities) {
    if (targets.length >= 6) break;
    targets.push(c);
  }

  return targets.length >= 2 ? targets : undefined;
}

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
