// Node preload shim for OpenWiki CI runs against OpenCode Go.
//
// OpenCode Go requires every client to identify its conversation with an
// `x-opencode-session` header (https://opencode.ai/docs/go/#where-can-i-use-it),
// otherwise requests are rejected with:
//   400 Request is missing x-opencode-session and cannot be routed efficiently.
//
// OpenWiki's `openai-compatible` provider has no way to configure extra request
// headers, so this module wraps the global fetch (which OpenWiki's provider
// delegates to) and adds the session header plus a non-generic user agent for
// requests to opencode.ai. Load it with:
//
//   NODE_OPTIONS="--import ./scripts/opencode-go-session-fetch.mjs"
//
// It is a no-op for every other origin.
import { randomUUID } from "node:crypto";

const OPENCODE_ORIGIN = "https://opencode.ai/";
const SESSION_ID = process.env.OPENCODE_GO_SESSION_ID ?? randomUUID();
const USER_AGENT = "openwiki-ci/1.0";

const originalFetch = globalThis.fetch;

function resolveUrl(input) {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  if (input && typeof input.url === "string") return input.url;
  return "";
}

globalThis.fetch = (input, init = {}) => {
  if (!resolveUrl(input).startsWith(OPENCODE_ORIGIN)) {
    return originalFetch(input, init);
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

  return originalFetch(input, { ...init, headers });
};
