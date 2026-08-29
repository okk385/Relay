# Development

## Requirements

- Python 3.11+
- Node.js 20+ for browser helper tests
- Chrome/Edge for extension smoke tests
- optional: `gh`, `tmux`, and Codex on the SSH host

## Test suite

```bash
python -m unittest discover -s tests -v
node --test browser-extension/tests/*.test.js
npm run check
```

## Local SSH smoke test

```bash
export RELAY_GITHUB_TOKEN=...
relay init --repo owner/repo --adapter stdout
relay setup-labels
relay once
```

Then add `relay:codex` to a test issue and run `relay once` again. The handoff should print once and remain in-flight until the label changes.

## Browser smoke test

1. Load `browser-extension/` as an unpacked extension.
2. Open a dedicated ChatGPT conversation and send one initial message so it has a stable URL.
3. Bind that tab in the extension popup.
4. Use **Test message**; the extension should insert and send a transport test.
5. Add `relay:chatgpt` to a GitHub test issue and choose **Poll now**.
6. Verify the handoff appears once and no assistant output is read by the extension.

## Product discipline

Before adding a feature, ask whether it belongs to ChatGPT/Codex or to cross-product transport. If a future OpenAI capability could replace the feature without changing the Relay protocol, implement it as an adapter or leave it to the agent.
