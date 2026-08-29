# Relay Protocol v0

Relay uses GitHub issue ownership labels as a durable, human-readable handoff protocol.

## Owner labels

Exactly one of these labels should be present on an active Relay issue:

| Label | Meaning |
|---|---|
| `relay:codex` | Codex owns the next action. |
| `relay:chatgpt` | ChatGPT owns the next action. |
| `relay:human` | A human must decide before automation continues. |
| `relay:done` | The task is complete and no agent should act. |

## Handoff identity

A handoff is identified by the GitHub issue-event ID created when an owner label is added.

```text
repo + issue + labeled-event-id
```

Relay clients store processed event IDs locally. This provides two properties:

1. Repeated polling does not repeat the same delivery.
2. Removing and later re-adding an owner label creates a new label event and a new handoff.

No Relay cloud or central queue is required.

## Transition rule

The current owner completes its work in GitHub, removes its owner label, and adds exactly one next-owner label.

```text
relay:codex   -> relay:chatgpt | relay:human | relay:done
relay:chatgpt -> relay:codex   | relay:human | relay:done
relay:human   -> relay:codex   | relay:chatgpt | relay:done
```

An agent may keep ownership while adding comments or commits. Relay does not infer completion from output, commit messages, CI, or elapsed time.

## One active issue per worker

V0 binds one SSH worker to one repository and allows only one in-flight `relay:codex` issue at a time. After a handoff is delivered, the worker waits until that issue no longer carries `relay:codex` before delivering another issue.

The browser uses the same rule for `relay:chatgpt`.

## Required task content

Relay does not interpret issue bodies, but a useful task normally contains:

- goal;
- source-of-truth commits/configs;
- constraints and explicit non-goals;
- expected outputs;
- validation requirements;
- stop/review conditions.

## ChatGPT behavior

When ChatGPT receives a Relay prompt:

1. Read the referenced issue and relevant repository state.
2. Perform planning, coding, or review using existing ChatGPT/GitHub capabilities.
3. Write all durable decisions to GitHub.
4. Remove `relay:chatgpt` and apply one next-owner label.

## Codex behavior

When Codex receives a Relay prompt:

1. Read the referenced issue and repository instructions.
2. Work normally in the real execution environment.
3. Write code, results, artifacts, and reports to GitHub as required by the issue.
4. Remove `relay:codex` and apply one next-owner label.

Relay does not prescribe whether Codex writes code, runs tests, submits an experiment, waits for compute, or requests human input.

## Human override

A human can always modify the issue or labels directly. `relay pause` pauses only automatic delivery; it does not stop Codex, shell commands, or experiments already running.
