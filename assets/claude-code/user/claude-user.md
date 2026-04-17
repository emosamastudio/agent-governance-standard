# Claude Code Global Governance

@../.agent-governance-standard/user/top-level-constraints.md
@../.agent-governance-standard/user/operating-model.md

## Claude-specific behavior

- Prefer the `claude-governed` wrapper so the top-level constraints are appended as a system prompt addition.
- When project `.agent-governance/` exists, treat it as the shared governance surface for mainline, sidelines, lifecycle state, and rule documents.
- Use project `CLAUDE.md` plus `.claude/settings.json` hooks as the runtime adapter layer.
