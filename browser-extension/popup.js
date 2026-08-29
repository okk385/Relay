const elements = {
  repository: document.querySelector("#repository"),
  githubToken: document.querySelector("#github-token"),
  pollInterval: document.querySelector("#poll-interval"),
  enabled: document.querySelector("#enabled"),
  boundUrl: document.querySelector("#bound-url"),
  status: document.querySelector("#status"),
  statusDot: document.querySelector("#status-dot"),
};

for (const [id, handler] of Object.entries({
  save: save,
  bind: () => request("relay:bind-current-tab"),
  poll: () => request("relay:poll-now"),
  test: () => request("relay:test-delivery"),
  clear: () => request("relay:clear-local-state"),
})) {
  document.querySelector(`#${id}`).addEventListener("click", async () => {
    await run(handler);
  });
}

await run(load);

async function request(type, extra = {}) {
  const response = await chrome.runtime.sendMessage({ type, ...extra });
  if (!response?.ok) throw new Error(response?.error || "Relay request failed");
  await load();
  return response.result;
}

async function load() {
  const response = await chrome.runtime.sendMessage({ type: "relay:get-settings" });
  if (!response?.ok) throw new Error(response?.error || "Could not load Relay settings");
  const settings = response.result;
  elements.repository.value = settings.repository ?? "";
  elements.githubToken.value = "";
  elements.githubToken.placeholder = settings.hasGithubToken
    ? "Token already stored; leave blank to keep it"
    : "Stored only in this browser profile";
  elements.pollInterval.value = settings.pollIntervalSeconds ?? 60;
  elements.enabled.checked = settings.enabled !== false;
  elements.boundUrl.textContent = settings.boundConversationUrl || "Not bound";
  renderStatus(settings.lastStatus);
}

async function save() {
  return request("relay:save-settings", {
    settings: {
      repository: elements.repository.value,
      githubToken: elements.githubToken.value,
      pollIntervalSeconds: Number(elements.pollInterval.value),
      enabled: elements.enabled.checked,
    },
  });
}

function renderStatus(status) {
  const state = status?.state ?? "unknown";
  elements.status.textContent = [state, status?.detail].filter(Boolean).join(" — ");
  elements.statusDot.dataset.state = state;
}

async function run(handler) {
  try {
    elements.status.textContent = "Working…";
    await handler();
  } catch (error) {
    elements.status.textContent = `Error — ${error.message}`;
    elements.statusDot.dataset.state = "error";
  }
}
