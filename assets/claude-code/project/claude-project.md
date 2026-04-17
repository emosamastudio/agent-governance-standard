# Claude Code Project Adapter

Use `.agent-governance/` as the shared project governance surface.

Follow these rule files:

- @.agent-governance/rules/00-global-governance.md
- @.agent-governance/rules/01-planning-and-parallelism.md
- @.agent-governance/rules/02-mainline-routing.md
- @.agent-governance/rules/03-lifecycle-observability.md
- @.agent-governance/rules/04-technology-research.md
- @.agent-governance/rules/05-acceptance-and-review.md
- @.agent-governance/rules/06-git-governance.md
- @.agent-governance/rules/07-hook-hardening.md

Runtime-specific requirements:

- Use `.claude/hooks/` as the hook adapter layer.
- Confirm and record `.agent-governance/state/delivery-intent.md` before deep planning or technology selection.
- Keep `.agent-governance/state/current-mainline.md` fresh enough that drift is detectable.
- Keep `.agent-governance/state/git-workflow.md` fresh enough that branch, push, PR, and merge behavior is governable.
- Keep the advanced hook gates active: `UserPromptSubmit`, `PermissionRequest`, `ConfigChange`, `Stop`, `TaskCompleted`, `SubagentStop`, `PreCompact`, and `PostCompact`.
- Use `.claude/bin/drift-check` before claiming the project is aligned.
