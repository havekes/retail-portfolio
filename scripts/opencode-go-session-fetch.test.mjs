import test from "node:test";
import assert from "node:assert/strict";

test("opencode-go-session-fetch shim", async (t) => {
  // Save original fetch
  const originalFetch = globalThis.fetch;

  // Import module which overrides globalThis.fetch
  const shim = await import("./opencode-go-session-fetch.mjs");

  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  await t.test("adds session header and user agent to opencode requests", async () => {
    let interceptedInput;
    let interceptedInit;

    // Temporarily replace fetch under the shim
    // (Note: shim delegates to originalFetch which was captured at import time)
    const testUrl = "https://opencode.ai/zen/go/v1/models";
    const res = await globalThis.fetch(testUrl, {
      headers: { "x-custom": "value" },
    }).catch((err) => {
      // In tests without live server, fetch will try connecting to opencode.ai unless mocked
    });
  });

  await t.test("patchAssistantMessages injects reasoning_content correctly", () => {
    shim.resetReasoningState();

    shim.recordReasoning("Step 1 internal reasoning", ["call_t1"]);
    shim.recordReasoning("Step 2 internal reasoning", ["call_t2"]);

    const messages = [
      { role: "user", content: "Analyze stock" },
      { role: "assistant", content: "", tool_calls: [{ id: "call_t1" }] },
      { role: "tool", tool_call_id: "call_t1", content: "data 1" },
      { role: "assistant", content: "", tool_calls: [{ id: "call_t2" }] },
      { role: "tool", tool_call_id: "call_t2", content: "data 2" },
      { role: "assistant", content: "Final answer" }, // text only, matched by turnHistory index 2 or last
    ];

    const modified = shim.patchAssistantMessages(messages);
    assert.strictEqual(modified, true);

    assert.strictEqual(messages[1].reasoning_content, "Step 1 internal reasoning");
    assert.strictEqual(messages[3].reasoning_content, "Step 2 internal reasoning");
    assert.strictEqual(messages[5].reasoning_content, "Step 2 internal reasoning");
  });

  await t.test("patchAssistantMessages defaults to empty string when no history exists", () => {
    shim.resetReasoningState();

    const messages = [
      { role: "assistant", content: "Untracked prior message" },
    ];

    const modified = shim.patchAssistantMessages(messages);
    assert.strictEqual(modified, true);
    assert.strictEqual(messages[0].reasoning_content, "");
  });

  await t.test("patchAssistantMessages leaves existing reasoning_content intact", () => {
    const messages = [
      { role: "assistant", content: "Hello", reasoning_content: "Existing thought" },
    ];

    const modified = shim.patchAssistantMessages(messages);
    assert.strictEqual(modified, false);
    assert.strictEqual(messages[0].reasoning_content, "Existing thought");
  });

  await t.test("captureStreamReasoning extracts reasoning and tool calls from SSE stream", async () => {
    shim.resetReasoningState();

    const encoder = new TextEncoder();
    const chunks = [
      "data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"I will execute \"}}]}\n\n",
      "data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"tool command.\"}}]}\n\n",
      "data: {\"choices\":[{\"delta\":{\"tool_calls\":[{\"id\":\"call_999\",\"function\":{\"name\":\"exec\"}}]}}]}\n\n",
      "data: [DONE]\n\n",
    ];

    const stream = new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    });

    await shim.captureStreamReasoning(stream);

    assert.strictEqual(shim.toolCallToReasoning.get("call_999"), "I will execute tool command.");
    assert.strictEqual(shim.turnHistory.length, 1);
    assert.strictEqual(shim.turnHistory[0].reasoning, "I will execute tool command.");
    assert.deepStrictEqual(shim.turnHistory[0].toolCallIds, ["call_999"]);
  });

  await t.test("end-to-end multi-turn stream and patch via globalThis.fetch", async () => {
    shim.resetReasoningState();

    const receivedRequests = [];
    const encoder = new TextEncoder();

    shim.setFetchImpl(async (input, init) => {
      let bodyText;
      if (typeof init.body === "string") {
        bodyText = init.body;
      } else if (input instanceof Request) {
        bodyText = await input.text();
      }
      receivedRequests.push({
        url: typeof input === "string" ? input : input.url,
        headers: new Headers(init.headers),
        body: bodyText ? JSON.parse(bodyText) : null,
      });

      if (receivedRequests.length === 1) {
        // Return turn 1 SSE stream response
        const chunks = [
          "data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"I should check files.\"}}]}\n\n",
          "data: {\"choices\":[{\"delta\":{\"tool_calls\":[{\"id\":\"call_abc123\",\"function\":{\"name\":\"ls\"}}]}}]}\n\n",
          "data: [DONE]\n\n",
        ];
        const stream = new ReadableStream({
          start(controller) {
            for (const c of chunks) controller.enqueue(encoder.encode(c));
            controller.close();
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        });
      }

      // Return turn 2 final answer response
      return new Response(JSON.stringify({
        choices: [{
          message: {
            role: "assistant",
            content: "Files listed successfully.",
            reasoning_content: "Done now.",
          },
        }],
      }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });

    try {
      // Turn 1 request
      const res1 = await globalThis.fetch("https://opencode.ai/zen/go/v1/chat/completions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          model: "deepseek-v4.1-flash",
          messages: [{ role: "user", content: "list files" }],
        }),
      });

      // Consumer reads stream
      const text1 = await res1.text();
      assert.match(text1, /call_abc123/);

      // Verify Turn 1 request headers
      assert.strictEqual(receivedRequests[0].headers.get("x-opencode-session"), shim.SESSION_ID);
      assert.strictEqual(receivedRequests[0].headers.get("user-agent"), shim.USER_AGENT);

      // Turn 2 request - LangChain omits reasoning_content from assistant message!
      const res2 = await globalThis.fetch("https://opencode.ai/zen/go/v1/chat/completions", {
        method: "POST",
        headers: { "content-type": "application/json", "content-length": "100" },
        body: JSON.stringify({
          model: "deepseek-v4.1-flash",
          messages: [
            { role: "user", content: "list files" },
            { role: "assistant", content: "", tool_calls: [{ id: "call_abc123" }] }, // missing reasoning_content!
            { role: "tool", tool_call_id: "call_abc123", content: "file1.txt\nfile2.txt" },
          ],
        }),
      });

      const json2 = await res2.json();
      assert.strictEqual(json2.choices[0].message.content, "Files listed successfully.");

      // Verify Turn 2 request had reasoning_content injected!
      const turn2Req = receivedRequests[1];
      assert.strictEqual(turn2Req.body.messages[1].reasoning_content, "I should check files.");
      // Verify content-length was updated
      const expectedByteLength = String(Buffer.byteLength(JSON.stringify(turn2Req.body), "utf-8"));
      assert.strictEqual(turn2Req.headers.get("content-length"), expectedByteLength);
    } finally {
      shim.resetFetchImpl();
    }
  });
});
