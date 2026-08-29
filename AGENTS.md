# Relay contributor instructions

Relay V0 is intentionally thin. Preserve these boundaries unless an issue explicitly changes the product contract.

## Product invariant

Relay transports handoffs. It does not make ChatGPT or Codex smarter and does not manage their internal work.

## In scope

- GitHub label-event polling
- binding one repository to one browser conversation / SSH worker
- delivery of a plain handoff message
- idempotency and crash-safe local state
- visible status, pause, resume, and diagnostics
- replaceable transport adapters

## Out of scope for V0

- reading or parsing ChatGPT assistant output
- reading or parsing Codex output
- planning, reviewing, retrying, or debugging on behalf of an agent
- Slurm or GPU scheduling/monitoring
- cloud accounts or a Relay backend
- MCP, ChatGPT plugin, or browser-page data extraction
- arbitrary remote shell execution
- multi-worker scheduling

## Engineering rules

- Keep Python runtime dependencies at zero unless a concrete issue justifies one.
- Use GitHub label event IDs as idempotency keys.
- Never mark an event processed before delivery succeeds.
- Do not deliver a second issue while the previous issue still owns the same relay label.
- Browser code may inspect composer availability but must never inspect assistant messages.
- Add tests for protocol or reliability changes.
- Run both Python and JavaScript tests before reporting completion.
