# Git, Branch, Push, PR, and Merge Governance

1. Git history is part of the engineering record, not a post-hoc packaging step.
2. Use commits to record meaningful design and development milestones:
   - planning baseline
   - architecture or technical decision shifts
   - coherent implementation slices
   - validation or review cleanup milestones
3. Avoid large, unstructured dump commits that hide design intent and recovery boundaries.
4. Keep the active git workflow explicit in `.agent-governance/state/git-workflow.md`.
5. Default branch model:
   - protected integration branch: `main` or `master`
   - working branches: `feat/*`, `fix/*`, `refactor/*`, `chore/*`, `research/*`, `review/*`, `hotfix/*`
6. Do not develop directly on a protected integration branch unless the repository intentionally uses a different protected-branch policy and that policy is documented.
7. Push only coherent states:
   - the scope is bounded
   - the branch is intentional
   - the next reviewer or agent can understand the milestone
8. PRs are required for integrating meaningful work into protected branches.
9. Before opening or merging a PR, the branch should have:
   - explicit acceptance criteria
   - current validation status
   - known review debt recorded
10. Merge management rules:
    - do not merge unresolved review debt silently
    - do not merge branches whose acceptance state is unclear
    - do not use merge operations that hide responsibility or destroy recovery clarity without a documented reason
11. If sideline work needs isolation, keep it on a separate branch rather than letting it pollute the mainline branch.
12. Commit messages should use structured prefixes such as:
    - `plan:`
    - `arch:`
    - `feat:`
    - `fix:`
    - `refactor:`
    - `test:`
    - `review:`
    - `docs:`
    - `chore:`
    - `merge:`
