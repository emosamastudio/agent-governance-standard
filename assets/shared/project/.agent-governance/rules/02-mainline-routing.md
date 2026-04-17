# Mainline and Sideline Routing

1. Maintain an explicit mainline at all times.
2. Classify every new instruction as:
   - mainline
   - sideline
   - defer / noise
3. The mainline is the only absolute path for the current phase.
4. Delegate bounded sideline work aggressively when possible.
5. When sideline work cannot be delegated, limit its scope, define its end condition, close it, then return to the mainline immediately.
6. Never let sideline context replace the mainline in memory or execution priority.
7. Keep `.agent-governance/state/current-mainline.md` current enough that drift can be detected.
