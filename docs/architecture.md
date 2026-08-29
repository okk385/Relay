# Relay V0 architecture

## Design goal

Remove the two manual messages that currently connect ChatGPT and Codex:

```text
"Codex, execute issue #N."
"ChatGPT, issue #N is ready for review."
```

## Components

### GitHub

GitHub is the only shared source of truth. Relay uses issue labels and label events for ownership and idempotency; agents use normal issues, comments, commits, pull requests, and artifacts for context.

### Relay Browser

The browser extension binds one open ChatGPT conversation to one repository. It polls for `relay:chatgpt`, inserts a plain review prompt, and clicks the normal send control.

It does not read assistant messages, infer completion, or copy model output anywhere. ChatGPT writes its durable result directly to GitHub.

### Relay SSH

The SSH worker polls for `relay:codex`, builds a plain issue-reference prompt, and passes it to a delivery adapter.

Adapters in V0:

- `stdout`: transport dry run;
- `tmux`: paste a message into a user-selected persistent terminal pane, without reading that pane;
- `command`: send the prompt on stdin to a user-configured command, such as a non-interactive Codex invocation.

The adapter boundary exists so a future official Codex transport can replace the V0 bridge without changing the GitHub protocol.

## Reliability model

Relay guarantees at-most-once local delivery for a GitHub label event after a confirmed transport success.

- Delivery failure: the event remains unprocessed and is retried.
- Relay restart: processed event IDs and the current in-flight issue are loaded from local state.
- Label unchanged after delivery: Relay waits; it does not send a second task.
- Label removed and re-added: GitHub creates a new event ID, enabling an intentional new handoff.

V0 does not claim distributed exactly-once delivery. A host can crash after an external transport accepts a message but before local state is committed. The visible GitHub protocol and dedicated agent windows make this recoverable; later adapters can add stronger acknowledgements.

## No cloud requirement

The browser and SSH worker independently poll GitHub over outbound HTTPS. Relay stores no source code, agent output, or account data on a Relay-operated server.
