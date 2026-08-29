import assert from "node:assert/strict";
import test from "node:test";

import {
  buildChatGPTPrompt,
  eventKey,
  latestLabelEvent,
  parseRepository,
} from "../lib.js";

test("parseRepository accepts owner/name", () => {
  assert.equal(parseRepository("openai/codex"), "openai/codex");
  assert.throws(() => parseRepository("codex"));
});

test("latestLabelEvent returns the newest matching event", () => {
  const event = latestLabelEvent(
    [
      { id: 4, event: "labeled", label: { name: "relay:chatgpt" } },
      { id: 9, event: "labeled", label: { name: "relay:chatgpt" } },
      { id: 10, event: "unlabeled", label: { name: "relay:chatgpt" } },
    ],
    "relay:chatgpt",
  );
  assert.equal(event.id, 9);
});

test("review prompt contains only durable GitHub references", () => {
  const prompt = buildChatGPTPrompt({
    repository: "owner/repo",
    issueNumber: 5,
    issueTitle: "Experiment complete",
    issueUrl: "https://github.com/owner/repo/issues/5",
    eventId: 123,
  });
  assert.match(prompt, /owner\/repo/);
  assert.match(prompt, /#5/);
  assert.match(prompt, /relay:codex/);
  assert.equal(eventKey(123), "github-label-event:123");
});
