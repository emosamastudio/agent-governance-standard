# GitHub Copilot CLI Project Governance

This repository uses `.agent-governance/` as the shared governance surface.

Required operating model:

1. Read `.agent-governance/rules/` before major implementation.
2. Confirm and record `.agent-governance/state/delivery-intent.md` before deep planning or technology selection.
3. Keep `.agent-governance/state/current-mainline.md` current enough that the active mainline is explicit.
4. Keep `.agent-governance/state/git-workflow.md` current enough that branch, push, PR, and merge intent is explicit.
5. Classify new requests into mainline, sideline, or defer before deep execution.
6. For multi-file work, default to `/plan` before implementation.
7. Prefer deep planning before `/fleet`, `/delegate`, or other parallel execution.
8. Use `/fleet` only for bounded, parallelizable tasks with explicit acceptance and clear delegation boundaries.
9. Use `/delegate` only for non-mainline or independently reviewable work.
10. Use commits as process records for planning, design, implementation, and cleanup milestones.
11. Use `/review` before calling significant work complete or ready for merge.
12. Do not treat implementation as complete until acceptance is defined and satisfied.
13. Record review and cleanup debt instead of letting it disappear.
