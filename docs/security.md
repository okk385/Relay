# Security notes

## Browser token

Relay Browser V0 stores a fine-grained GitHub token in `chrome.storage.local` for the current browser profile. Use a dedicated token limited to the selected repository with read-only access to metadata and issues.

Do not use a broad classic personal access token.

The extension requests host access only for:

- `https://api.github.com/*`
- `https://chatgpt.com/*`

## SSH token

Relay SSH resolves credentials from:

1. `RELAY_GITHUB_TOKEN`;
2. `GITHUB_TOKEN`;
3. `gh auth token`.

The token must be able to read issues and issue events. `relay setup-labels` additionally needs permission to create labels.

Tokens are not written into Relay config or state files.

## ChatGPT boundary

The content script only:

- finds the visible prompt composer;
- refuses to overwrite a non-empty draft;
- inserts the handoff text;
- activates the normal send control.

It does not query, scrape, parse, or export assistant messages.

## Codex boundary

The SSH worker never reads Codex output. The `tmux` adapter only writes one prompt to a user-selected pane. The `command` adapter invokes only the exact argv stored in local config and sends the prompt on stdin; Relay does not expose a network shell API.

## Human control

Use a dedicated ChatGPT conversation and a dedicated tmux pane. The user remains able to pause Relay, edit GitHub ownership labels, or interact with either agent directly.
