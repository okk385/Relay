export const CHATGPT_LABEL = "relay:chatgpt";

export function parseRepository(value) {
  const trimmed = String(value ?? "").trim();
  const parts = trimmed.split("/");
  if (parts.length !== 2 || parts.some((part) => !part)) {
    throw new Error("Repository must use owner/name form");
  }
  if (parts.some((part) => !/^[A-Za-z0-9._-]+$/.test(part))) {
    throw new Error("Repository contains unsupported characters");
  }
  return trimmed;
}

export function latestLabelEvent(events, label) {
  const matches = events.filter(
    (event) =>
      event?.event === "labeled" &&
      event?.label?.name === label &&
      Number.isInteger(Number(event?.id)),
  );
  if (matches.length === 0) return null;
  return matches.reduce((latest, event) =>
    Number(event.id) > Number(latest.id) ? event : latest,
  );
}

export function buildChatGPTPrompt(handoff) {
  return [
    "RELAY HANDOFF — CODEX TO CHATGPT",
    "",
    `Repository: ${handoff.repository}`,
    `Issue: #${handoff.issueNumber} — ${handoff.issueTitle}`,
    `URL: ${handoff.issueUrl}`,
    `Handoff event: ${handoff.eventId}`,
    "",
    "Codex has transferred this task to ChatGPT.",
    "Read the GitHub issue, relevant commits, comments, and artifacts; perform the appropriate review or planning work.",
    "",
    "When your part is complete, update GitHub and leave exactly one next-owner label:",
    "- `relay:codex` when Codex should continue,",
    "- `relay:human` when a human decision is required,",
    "- `relay:done` when the task is complete.",
    "Remove `relay:chatgpt` during the ownership transition.",
  ].join("\n");
}

export function eventKey(eventId) {
  return `github-label-event:${Number(eventId)}`;
}
