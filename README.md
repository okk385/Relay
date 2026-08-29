# Relay

Relay is a Git-native handoff layer between a dedicated ChatGPT browser conversation and Codex running on an SSH research server.

> ChatGPT plans. Codex runs. You stay in control.

## V0 architecture

```text
ChatGPT tab <-- Relay Browser --> GitHub <-- Relay SSH --> Codex / SSH / HPC
```

Relay does **not** plan tasks, inspect model output, manage Slurm, or replace either agent. GitHub remains the source of truth; Relay only transports ownership changes.

### Components

- **Relay Browser**: a Chrome/Edge Manifest V3 extension that polls GitHub for `relay:chatgpt` handoffs and inserts a review request into one user-bound ChatGPT conversation. It never reads assistant responses.
- **Relay SSH**: a small Python CLI that polls GitHub for `relay:codex` handoffs and delivers the issue reference through a configured adapter (`tmux`, `command`, or `stdout`). It never parses Codex output.
- **Relay Protocol**: four GitHub labels and label-event IDs used for ownership and idempotency.

## Protocol labels

- `relay:codex` — Codex owns the next action.
- `relay:chatgpt` — ChatGPT owns the next action.
- `relay:human` — a person must decide.
- `relay:done` — the task is complete.

See [`protocol/README.md`](protocol/README.md) for the state and handoff rules.

## Quick start

### 1. Install the browser extension locally

1. Open `chrome://extensions` (or `edge://extensions`).
2. Enable Developer mode.
3. Choose **Load unpacked** and select `browser-extension/`.
4. Open a dedicated ChatGPT conversation.
5. Open the Relay extension, enter a fine-grained GitHub token and `owner/repo`, then bind the current tab.

For V0, the token should have read access to repository metadata and issues only.

### 2. Install Relay SSH

```bash
python -m pip install -e .
relay init --repo owner/repo --adapter tmux --tmux-target relay-codex:0.0
relay setup-labels
relay start
```

Relay resolves a GitHub token from `RELAY_GITHUB_TOKEN`, `GITHUB_TOKEN`, or `gh auth token` (in that order).

For a dry run:

```bash
relay init --repo owner/repo --adapter stdout
relay once
```

### 3. Transfer ownership through GitHub

A ChatGPT-created task becomes available to Codex when the issue receives `relay:codex`. Codex writes its report to GitHub, removes that label, and adds `relay:chatgpt`. Re-adding the same label creates a new GitHub label event and therefore a new handoff.

## Development

```bash
python -m unittest discover -s tests -v
node --test browser-extension/tests/*.test.js
node --check browser-extension/background.js
node --check browser-extension/content.js
node --check browser-extension/popup.js
```

## V0 boundaries

Relay V0 deliberately has no cloud service, no MCP server, no ChatGPT plugin, no model, no scheduler, no output scraping, and no shell proxy. The browser bridge and `tmux` adapter are replaceable transport adapters; the GitHub protocol is the durable product core.

## Status

Early dogfood implementation. The first target is a real multi-issue ChatGPT ↔ Codex research workflow.

## License

To be selected before the first public release.
