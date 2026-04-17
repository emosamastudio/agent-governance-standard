# Hook Hardening Policy

1. If an agent framework supports hooks, use them as active governance controls, not only passive logging.
2. Hook coverage should be strongest at these control points:
   - session start
   - task or subagent creation
   - pre-tool execution
   - post-tool execution
   - stop / completion
   - session end
3. Hook responsibilities should include:
   - lifecycle logging
   - safety checks
   - mainline drift checks
   - delegation gating
   - git workflow protection
   - completion gate reminders
4. Blocking hooks should be used when the action would violate core governance, especially for:
   - unsafe destructive commands
   - delegation before planning is saturated
   - direct pushes or merges to protected branches
   - missing mainline or git workflow state before parallel execution
5. Non-blocking hooks should still emit context when the system is drifting but the action does not yet justify a hard block.
6. Hook logic must be explicit, versioned, and reviewable; do not hide governance in opaque runtime behavior.
7. When a runtime does not support hooks, document the gap and approximate the behavior through its native instruction system.
