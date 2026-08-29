import {
  CHATGPT_LABEL,
  buildChatGPTPrompt,
  eventKey,
  latestLabelEvent,
  parseRepository,
} from "./lib.js";

const ALARM_NAME = "relay-poll";
const DEFAULTS = {
  enabled: true,
  repository: "",
  githubToken: "",
  boundTabId: null,
  boundConversationUrl: "",
  pollIntervalSeconds: 60,
  processedEventKeys: [],
  inflight: null,
  lastStatus: { state: "not-configured", at: null, detail: null },
};

chrome.runtime.onInstalled.addListener(async () => {
  const stored = await chrome.storage.local.get(DEFAULTS);
  await chrome.storage.local.set(stored);
  await refreshAlarm(stored.pollIntervalSeconds);
});

chrome.runtime.onStartup.addListener(async () => {
  const settings = await getSettings();
  await refreshAlarm(settings.pollIntervalSeconds);
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    pollRelay().catch((error) => setStatus("error", error.message));
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  handleMessage(message)
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));
  return true;
});

async function handleMessage(message) {
  switch (message?.type) {
    case "relay:get-settings":
      return sanitizeForPopup(await getSettings());
    case "relay:save-settings":
      return saveSettings(message.settings ?? {});
    case "relay:bind-current-tab":
      return bindCurrentTab();
    case "relay:poll-now":
      return pollRelay();
    case "relay:test-delivery":
      return testDelivery();
    case "relay:clear-local-state":
      await chrome.storage.local.set({ processedEventKeys: [], inflight: null });
      return sanitizeForPopup(await getSettings());
    default:
      throw new Error("Unknown Relay message");
  }
}

async function getSettings() {
  return chrome.storage.local.get(DEFAULTS);
}

function sanitizeForPopup(settings) {
  return {
    ...settings,
    githubToken: settings.githubToken ? "••••••••" : "",
    hasGithubToken: Boolean(settings.githubToken),
  };
}

async function saveSettings(input) {
  const current = await getSettings();
  const repository = parseRepository(input.repository ?? current.repository);
  const pollIntervalSeconds = Math.max(
    30,
    Number(input.pollIntervalSeconds ?? current.pollIntervalSeconds ?? 60),
  );
  const next = {
    ...current,
    repository,
    enabled: input.enabled ?? current.enabled,
    pollIntervalSeconds,
  };
  if (typeof input.githubToken === "string" && input.githubToken.trim()) {
    next.githubToken = input.githubToken.trim();
  }
  await chrome.storage.local.set(next);
  await refreshAlarm(pollIntervalSeconds);
  return sanitizeForPopup(next);
}

async function refreshAlarm(seconds) {
  await chrome.alarms.clear(ALARM_NAME);
  await chrome.alarms.create(ALARM_NAME, {
    periodInMinutes: Math.max(0.5, Number(seconds || 60) / 60),
  });
}

async function bindCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url?.startsWith("https://chatgpt.com/")) {
    throw new Error("Open the dedicated ChatGPT Relay conversation before binding");
  }
  await chrome.storage.local.set({
    boundTabId: tab.id,
    boundConversationUrl: tab.url,
  });
  await setStatus("bound", `Bound tab ${tab.id}`);
  return sanitizeForPopup(await getSettings());
}

async function githubRequest(settings, path) {
  if (!settings.githubToken) {
    throw new Error("GitHub token is missing");
  }
  const response = await fetch(`https://api.github.com${path}`, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${settings.githubToken}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`GitHub API failed (${response.status}): ${detail.slice(0, 240)}`);
  }
  return response.json();
}

async function listIssueEvents(settings, issueNumber) {
  const events = [];
  for (let page = 1; page <= 10; page += 1) {
    const batch = await githubRequest(
      settings,
      `/repos/${settings.repository}/issues/${issueNumber}/events?per_page=100&page=${page}`,
    );
    events.push(...batch);
    if (batch.length < 100) break;
  }
  return events;
}

async function findBoundTab(settings) {
  if (settings.boundTabId != null) {
    try {
      const tab = await chrome.tabs.get(settings.boundTabId);
      if (tab?.url?.startsWith("https://chatgpt.com/")) return tab;
    } catch (_error) {
      // Fall through to URL lookup.
    }
  }
  const tabs = await chrome.tabs.query({ url: "https://chatgpt.com/*" });
  const match = tabs.find((tab) =>
    settings.boundConversationUrl
      ? tab.url === settings.boundConversationUrl
      : Boolean(tab.url),
  );
  if (match?.id) {
    await chrome.storage.local.set({ boundTabId: match.id });
    return match;
  }
  return null;
}

async function pollRelay() {
  const settings = await getSettings();
  if (!settings.enabled) {
    await setStatus("paused", "Browser relay is disabled");
    return { state: "paused" };
  }
  if (!settings.repository || !settings.githubToken) {
    await setStatus("not-configured", "Repository or GitHub token missing");
    return { state: "not-configured" };
  }

  const encodedLabel = encodeURIComponent(CHATGPT_LABEL);
  const issues = await githubRequest(
    settings,
    `/repos/${settings.repository}/issues?state=open&labels=${encodedLabel}&per_page=100&sort=created&direction=asc`,
  );
  const issueOnly = issues.filter((issue) => !issue.pull_request);

  if (settings.inflight) {
    const stillOwned = issueOnly.some(
      (issue) => Number(issue.number) === Number(settings.inflight.issueNumber),
    );
    if (stillOwned) {
      await setStatus(
        "waiting-for-owner-transition",
        `Issue #${settings.inflight.issueNumber} still has ${CHATGPT_LABEL}`,
      );
      return { state: "waiting-for-owner-transition" };
    }
    settings.inflight = null;
    await chrome.storage.local.set({ inflight: null });
  }

  const processed = new Set(settings.processedEventKeys ?? []);
  const candidates = [];
  for (const issue of issueOnly) {
    const event = latestLabelEvent(
      await listIssueEvents(settings, Number(issue.number)),
      CHATGPT_LABEL,
    );
    if (!event || processed.has(eventKey(event.id))) continue;
    candidates.push({ issue, event });
  }
  candidates.sort((a, b) =>
    String(a.event.created_at ?? "").localeCompare(String(b.event.created_at ?? "")) ||
    Number(a.event.id) - Number(b.event.id),
  );

  if (candidates.length === 0) {
    await setStatus("idle", "No ChatGPT handoff is pending");
    return { state: "idle" };
  }

  const { issue, event } = candidates[0];
  const handoff = {
    repository: settings.repository,
    issueNumber: Number(issue.number),
    issueTitle: String(issue.title ?? ""),
    issueUrl: String(issue.html_url ?? ""),
    eventId: Number(event.id),
  };
  const tab = await findBoundTab(settings);
  if (!tab?.id) {
    await notify("Relay needs ChatGPT", "Open the bound ChatGPT conversation to receive the handoff.");
    throw new Error("Bound ChatGPT conversation is not open");
  }

  const response = await chrome.tabs.sendMessage(tab.id, {
    type: "relay:deliver-to-chatgpt",
    prompt: buildChatGPTPrompt(handoff),
  });
  if (!response?.ok) {
    throw new Error(response?.error || "ChatGPT page did not accept the handoff");
  }

  const nextProcessed = [...processed, eventKey(event.id)].slice(-2000);
  const inflight = {
    issueNumber: handoff.issueNumber,
    eventId: handoff.eventId,
    deliveredAt: new Date().toISOString(),
  };
  await chrome.storage.local.set({
    processedEventKeys: nextProcessed,
    inflight,
  });
  await setStatus("delivered", `Codex -> ChatGPT: issue #${handoff.issueNumber}`);
  return { state: "delivered", handoff };
}

async function testDelivery() {
  const settings = await getSettings();
  const tab = await findBoundTab(settings);
  if (!tab?.id) throw new Error("Bound ChatGPT conversation is not open");
  const response = await chrome.tabs.sendMessage(tab.id, {
    type: "relay:deliver-to-chatgpt",
    prompt: [
      "RELAY TRANSPORT TEST",
      "",
      "This is a local browser-bridge smoke test. Do not change GitHub or start any task.",
      "Reply only that the Relay Browser message arrived.",
    ].join("\n"),
  });
  if (!response?.ok) throw new Error(response?.error || "Test delivery failed");
  await setStatus("test-delivered", "Test prompt sent to ChatGPT");
  return { state: "test-delivered" };
}

async function setStatus(state, detail = null) {
  const status = { state, detail, at: new Date().toISOString() };
  await chrome.storage.local.set({ lastStatus: status });
  return status;
}

async function notify(title, message) {
  try {
    await chrome.notifications.create({
      type: "basic",
      iconUrl: "icon.svg",
      title,
      message,
    });
  } catch (_error) {
    // Notifications are best effort; polling must continue without them.
  }
}
