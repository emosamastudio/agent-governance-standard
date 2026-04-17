# Lifecycle, Logs, and Hooks

1. The project must have a defined lifecycle before implementation begins.
2. Each important lifecycle node should be observable and hookable.
3. Lifecycle logs belong under `.agent-governance/state/lifecycle/`.
4. Logs should capture:
   - state changes
   - key decisions
   - tool activity
   - subagent dispatch
   - review outcomes
   - failures
   - completion signals
5. If a governance rule cannot be automated yet, record it and keep the gap visible.
