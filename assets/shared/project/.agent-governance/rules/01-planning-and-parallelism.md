# Planning Before Parallel Execution

1. Before planning, confirm the delivery intent with the user:
   - final-system build
   - fast MVP
2. Record that choice in `.agent-governance/state/delivery-intent.md` and let it guide all later reasoning.
3. Prefer comprehensive, deep, saturated planning before execution, but scale the plan depth and scope according to the recorded delivery intent.
4. Do not dispatch subagents while the task graph, dependencies, boundaries, and acceptance are still vague.
5. The primary agent owns:
   - global understanding
   - architecture
   - decomposition
   - dependency planning
   - acceptance design
6. Subagents are for bounded execution threads, not for replacing mainline thinking.
7. If new information invalidates the existing decomposition, pause blind parallelism and re-plan.
