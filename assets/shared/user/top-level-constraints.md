# Top-Level Constraints

- Optimize for the best final system, not the fastest local implementation.
- Before planning and technology selection, confirm whether the user wants a final-system build or a fast MVP. Do not infer this implicitly.
- Define goal, architecture, lifecycle, and acceptance before implementation.
- Plan deeply before parallel execution; use subagents only after boundaries, dependencies, and acceptance are explicit.
- Maintain a strict mainline; classify every new request as mainline, sideline, or defer, and do not let sidelines consume the mission.
- Preserve lifecycle logs, hookable checkpoints, auditability, and reviewability.
- Use commits to preserve design and development history; keep branch, push, PR, and merge flow governed instead of ad hoc.
- Perform live cognition checks during technology selection; if new knowledge changes the landscape, revisit the plan and the stack.
- Completion requires acceptance, review, cleanup capture, and continued alignment with the mainline.
