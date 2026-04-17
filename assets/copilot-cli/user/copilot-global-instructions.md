# GitHub Copilot CLI Global Governance

Apply these constraints in all repositories unless a narrower repository rule overrides them:

1. Optimize for the final system, not the fastest local implementation.
2. Before planning and technology selection, confirm whether the user wants a final-system build or a fast MVP.
3. Before implementation, make the goal, architecture, lifecycle, and acceptance criteria explicit.
4. Plan deeply before parallel execution.
5. Keep a strict distinction between mainline, sidelines, and deferred work.
6. Do not let sideline work consume the session and displace the mainline.
7. Re-check technology choices when new knowledge changes the best path.
8. Treat logs, review, and cleanup as part of completion.

When a repository contains `.agent-governance/`, use it as the shared governance surface.

Prefer launching Copilot through `~/.copilot/bin/copilot-governed` so the strongest allow/deny tool baseline is active by default.
