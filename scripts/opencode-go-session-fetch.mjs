// Node preload shim for OpenWiki CI runs against OpenCode Go.
//
// 1. Session and Routing:
//    OpenCode Go requires every client to identify its conversation with an
//    `x-opencode-session` header (https://opencode.ai/docs/go/#where-can-i-use-it),
//    otherwise requests are rejected with:
//      400 Request is missing x-opencode-session and cannot be routed efficiently.
//
// 2. Thinking Mode Reasoning Round-Trip:
//    Reasoning models like DeepSeek V4.1 Flash (`deepseek-v4.1-flash`) operate in
//    thinking mode and strictly require `reasoning_content` from previous assistant
//    turns to be included in multi-turn requests / tool-use loops. Otherwise:
//      400 Upstream request failed: [invalid_request_error] The `reasoning_content`
//      in the thinking mode must be passed back to the API.
//
//    OpenWiki's underlying `@langchain/openai` provider serializes assistant messages
//    with `role`, `content`, and `tool_calls`, but drops `reasoning_content`.
//    This shim intercepts incoming SSE and JSON responses to capture `reasoning_content`
//    (associated with tool calls and turn order) and injects it back into outgoing
//    assistant message payloads before sending them to OpenCode Go.
//
// Load it with:
//   NODE_OPTIONS="--import ./scripts/opencode-go-session-fetch.mjs"
//
// It is a no-op for every other origin.
import { randomUUID } from "node:crypto";

const OPENCODE_ORIGIN = "https://opencode.ai/";
const SESSION_ID = process.env.OPENCODE_GO_SESSION_ID ?? randomUUID();
const USER_AGENT = "openwiki-ci/1.0";

const originalFetch = globalThis.fetch;
let fetchImpl = originalFetch;

function setFetchImpl(fn) {
  fetchImpl = fn;
}

function resetFetchImpl() {
  fetchImpl = originalFetch;
}

function resolveUrl(input) {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  if (input && typeof input.url === "string") return input.url;
  return "";
}

// Conversation reasoning state across turns in this session:
const toolCallToReasoning = new Map();
const turnHistory = [];
let lastCapturedReasoning = "";

function recordReasoning(reasoning, toolCallIds = []) {
  lastCapturedReasoning = reasoning;
  turnHistory.push({ reasoning, toolCallIds: [...toolCallIds] });
  for (const id of toolCallIds) {
    toolCallToReasoning.set(id, reasoning);
  }
}

function resetReasoningState() {
  toolCallToReasoning.clear();
  turnHistory.length = 0;
  lastCapturedReasoning = "";
}

function patchAssistantMessages(messages) {
  let modified = false;
  let assistantIndex = 0;

  for (const msg of messages) {
    if (msg && msg.role === "assistant") {
      if (msg.reasoning_content === undefined || msg.reasoning_content === null) {
        let reasoning;

        // 1. Try matching by tool_call_id
        if (Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0) {
          for (const tc of msg.tool_calls) {
            if (tc?.id && toolCallToReasoning.has(tc.id)) {
              reasoning = toolCallToReasoning.get(tc.id);
              break;
            }
          }
        }

        // 2. Try matching by assistant turn sequence
        if (reasoning === undefined && assistantIndex < turnHistory.length) {
          reasoning = turnHistory[assistantIndex].reasoning;
        }

        // 3. Fallback to last captured reasoning
        if (reasoning === undefined && lastCapturedReasoning) {
          reasoning = lastCapturedReasoning;
        }

        // 4. Default to empty string to ensure key is present
        if (reasoning === undefined) {
          reasoning = "";
        }

        msg.reasoning_content = reasoning;
        modified = true;
      }
      assistantIndex++;
    }
  }

  return modified;
}

async function captureStreamReasoning(stream) {
  try {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let accumulatedReasoning = "";
    const toolCallIds = new Set();
    let recorded = false;

    const finish = () => {
      if (recorded) return;
      recorded = true;
      recordReasoning(accumulatedReasoning, toolCallIds);
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const data = trimmed.slice(5).trim();
        if (data === "[DONE]") {
          finish();
          return;
        }
        try {
          const json = JSON.parse(data);
          const delta = json.choices?.[0]?.delta;
          if (delta) {
            const reasoning = delta.reasoning_content ?? delta.reasoning;
            if (reasoning) {
              accumulatedReasoning += reasoning;
            }
            if (Array.isArray(delta.tool_calls)) {
              for (const tc of delta.tool_calls) {
                if (tc?.id) {
                  toolCallIds.add(tc.id);
                }
              }
            }
          }
        } catch {
          // Ignore JSON parse errors in malformed stream lines
        }
      }
    }

    if (buffer) {
      const trimmed = buffer.trim();
      if (trimmed.startsWith("data:")) {
        const data = trimmed.slice(5).trim();
        if (data && data !== "[DONE]") {
          try {
            const json = JSON.parse(data);
            const delta = json.choices?.[0]?.delta;
            if (delta) {
              const reasoning = delta.reasoning_content ?? delta.reasoning;
              if (reasoning) {
                accumulatedReasoning += reasoning;
              }
              if (Array.isArray(delta.tool_calls)) {
                for (const tc of delta.tool_calls) {
                  if (tc?.id) toolCallIds.add(tc.id);
                }
              }
            }
          } catch {}
        }
      }
    }

    finish();
  } catch {
    // If stream reading fails or is aborted, ignore safely
  }
}

globalThis.fetch = async (input, init = {}) => {
  const url = resolveUrl(input);
  if (!url.startsWith(OPENCODE_ORIGIN)) {
    return fetchImpl(input, init);
  }

  const headers = new Headers(
    init.headers ?? (input instanceof Request ? input.headers : undefined),
  );
  if (!headers.has("x-opencode-session")) {
    headers.set("x-opencode-session", SESSION_ID);
  }
  // Identify the client per the OpenCode Go guidelines instead of inheriting a
  // generic SDK/HTTP-library user agent.
  headers.set("user-agent", USER_AGENT);

  const nextInit = { ...init, headers };

  // Check and patch chat completion messages in request body:
  try {
    let bodyText;
    if (init.body) {
      if (typeof init.body === "string") {
        bodyText = init.body;
      } else if (Buffer.isBuffer(init.body) || init.body instanceof Uint8Array) {
        bodyText = Buffer.from(init.body).toString("utf-8");
      }
    } else if (input instanceof Request) {
      bodyText = await input.clone().text();
    }

    if (bodyText) {
      const payload = JSON.parse(bodyText);
      if (payload && Array.isArray(payload.messages)) {
        const modified = patchAssistantMessages(payload.messages);
        if (modified) {
          const newBody = JSON.stringify(payload);
          nextInit.body = newBody;
          if (headers.has("content-length")) {
            headers.set("content-length", String(Buffer.byteLength(newBody, "utf-8")));
          }
        }
      }
    }
  } catch {
    // Non-JSON or unreadable body, proceed unchanged
  }

  const requestInput = (input instanceof Request && nextInit.body !== undefined)
    ? new Request(input, nextInit)
    : input;

  const response = await fetchImpl(requestInput, nextInit);

  // Capture reasoning_content from successful responses:
  if (response.ok && response.body && url.includes("/chat/completions")) {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("text/event-stream")) {
      const [clientStream, captureStream] = response.body.tee();
      captureStreamReasoning(captureStream);
      return new Response(clientStream, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    } else if (contentType.includes("application/json")) {
      response.clone().json().then((data) => {
        const msg = data?.choices?.[0]?.message;
        if (msg) {
          const reasoning = msg.reasoning_content ?? msg.reasoning ?? "";
          const toolCallIds = new Set();
          if (Array.isArray(msg.tool_calls)) {
            for (const tc of msg.tool_calls) {
              if (tc?.id) toolCallIds.add(tc.id);
            }
          }
          recordReasoning(reasoning, toolCallIds);
        }
      }).catch(() => {});
    }
  }

  return response;
};

export {
  SESSION_ID,
  USER_AGENT,
  OPENCODE_ORIGIN,
  recordReasoning,
  resetReasoningState,
  setFetchImpl,
  resetFetchImpl,
  patchAssistantMessages,
  captureStreamReasoning,
  toolCallToReasoning,
  turnHistory,
};
