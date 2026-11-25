import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

// Transpile frontend/src/lib/chatHistory.ts in memory using project TypeScript compiler (no new test deps)
const srcPath = path.resolve("src/lib/chatHistory.ts");
const tsSource = fs.readFileSync(srcPath, "utf8");
const { outputText } = ts.transpileModule(tsSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
});
const mod = { exports: {} };
new Function("module", "exports", outputText)(mod, mod.exports);
const {
  buildOutboundChatHistory,
  classifyApiErrorMessage,
  MAX_CHAT_TURNS,
  MAX_CHAT_MESSAGE_CHARS,
  SAFE_AGGREGATE_HISTORY_CHARS,
} = mod.exports;

test("buildOutboundChatHistory excludes local-only messages and keeps 1-turn valid", () => {
  const history = buildOutboundChatHistory([
    { role: "assistant", content: "Welcome!", isLocalOnly: true },
    { role: "user", content: "Is it raining?" },
    {
      role: "assistant",
      content: "Full 1000-char reply...",
      historyContent: "Server summary (UNSUPPORTED_WEATHER) for Chennai.",
      attestation: "a".repeat(64),
    },
  ]);
  assert.equal(history.length, 2);
  assert.equal(history[0].role, "user");
  assert.equal(history[1].content, "Server summary (UNSUPPORTED_WEATHER) for Chennai.");
  assert.equal(history[1].attestation, "a".repeat(64));
});

test("buildOutboundChatHistory trims oldest turns first below aggregate char safety budget", () => {
  const messages = [];
  for (let i = 0; i < 12; i++) {
    messages.push({ role: "user", content: `Question ${i}: ` + "q".repeat(180) });
    messages.push({
      role: "assistant",
      content: "Full verbose reply...",
      historyContent: `Reply ${i}: ` + "r".repeat(250),
      attestation: "b".repeat(64),
    });
  }
  const outbound = buildOutboundChatHistory(messages);
  assert.ok(outbound.length <= MAX_CHAT_TURNS);
  const totalChars = outbound.reduce((sum, t) => sum + t.content.length, 0);
  assert.ok(totalChars <= SAFE_AGGREGATE_HISTORY_CHARS, `Expected <= ${SAFE_AGGREGATE_HISTORY_CHARS}, got ${totalChars}`);
  // Newest turns preserved
  assert.match(outbound[outbound.length - 1].content, /^Reply 11:/);
});

test("buildOutboundChatHistory drops oversized single turn rather than truncating mid-sentence", () => {
  const outbound = buildOutboundChatHistory([
    { role: "user", content: "ok" },
    { role: "assistant", content: "x".repeat(MAX_CHAT_MESSAGE_CHARS + 50) },
    { role: "user", content: "What about PM2.5?" },
  ]);
  assert.equal(outbound.length, 2);
  assert.equal(outbound[0].content, "ok");
  assert.equal(outbound[1].content, "What about PM2.5?");
});

// Load api.ts too via TypeScript transpiler (with mocked relative ./chatHistory and fetch)
const apiPath = path.resolve("src/lib/api.ts");
const apiSource = fs.readFileSync(apiPath, "utf8");
const { outputText: apiJs } = ts.transpileModule(apiSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
});

function loadApiWithMockFetch(mockFetch) {
  const apiMod = { exports: {} };
  const reqFn = (id) => {
    if (id === "./chatHistory") return mod.exports;
    throw new Error(`Unexpected require: ${id}`);
  };
  new Function("module", "exports", "process", "fetch", "URLSearchParams", "require", apiJs)(
    apiMod,
    apiMod.exports,
    { env: {} },
    mockFetch,
    URLSearchParams,
    reqFn
  );
  return apiMod.exports;
}

test("sendAIChat handles one-turn deterministic fallback without Gemini and forwards activity/sensitivity", async () => {
  let capturedBody = null;
  const mockFetch = async (_url, init) => {
    capturedBody = JSON.parse(init.body);
    return {
      ok: true,
      status: 200,
      json: async () => ({
        reply: "In New Delhi...",
        grounded_in_data: true,
        explanation_mode: "deterministic_fallback",
        model_used: "deterministic-fallback",
        llm_fallback_used: true,
        llm_fallback_reason: "LLM API key not configured",
        prompt_injection_detected: false,
        verified_context: {},
        sources_cited: [],
        warnings: [],
        history_summary: "Server summary...",
        reply_attestation: "c".repeat(64),
        disclaimer: "Disclaimer",
      }),
    };
  };
  const { sendAIChat } = loadApiWithMockFetch(mockFetch);
  const res = await sendAIChat({
    message: "Is outdoor running advisable?",
    city: "New Delhi",
    activity: "running",
    sensitivity_preference: "respiratory",
    chat_history: [{ role: "assistant", content: "Welcome!", isLocalOnly: true }],
  });
  assert.equal(res.explanation_mode, "deterministic_fallback");
  assert.equal(capturedBody.activity, "running");
  assert.equal(capturedBody.sensitivity_preference, "respiratory");
  assert.equal(capturedBody.chat_history.length, 0);
});

test("sendAIChat propagates HTTP 422 ApiError cleanly distinct from network errors", async () => {
  const { sendAIChat } = loadApiWithMockFetch(async () => ({
    ok: false,
    status: 422,
    json: async () => ({
      detail: [{ msg: "Question message exceeds maximum limit (1000 characters)." }],
    }),
  }));
  await assert.rejects(
    () => sendAIChat({ message: "x".repeat(1200), city: "New Delhi", chat_history: [] }),
    (err) => {
      const classified = classifyApiErrorMessage(err);
      assert.equal(classified.kind, "validation");
      assert.match(classified.message, /HTTP 422/);
      assert.match(classified.message, /1000 characters/);
      return true;
    }
  );
});

test("classifyApiErrorMessage distinguishes HTTP 422, 429, 503, and genuine network errors", () => {
  const err422 = Object.assign(new Error("Aggregate chat_history size exceeded"), { status: 422 });
  const c422 = classifyApiErrorMessage(err422);
  assert.equal(c422.kind, "validation");
  assert.match(c422.message, /HTTP 422/);
  assert.doesNotMatch(c422.message, /AI inference service/i);

  const err503 = Object.assign(new Error("Provider unavailable"), { status: 503 });
  const c503 = classifyApiErrorMessage(err503);
  assert.equal(c503.kind, "server");
  assert.match(c503.message, /HTTP 503/);

  const netErr = new TypeError("Failed to fetch");
  const cNet = classifyApiErrorMessage(netErr);
  assert.equal(cNet.kind, "network");
  assert.match(cNet.message, /network or connectivity error/i);
});
