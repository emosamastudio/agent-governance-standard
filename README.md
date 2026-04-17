# Agent Governance Standard

Portable, one-command governance bootstrap for multiple coding agents.

**Supported first-class adapters**

- Claude Code CLI
- GitHub Copilot CLI

The standard is **agent-agnostic at the core**:

- shared top-level constraints
- shared operating model
- shared project governance surface
- runtime adapters for each agent CLI
- shared git / branch / PR / merge governance

## Install

Remote one-command install shared core + both supported adapters:

```bash
curl -fsSL https://raw.githubusercontent.com/emosamastudio/agent-governance-standard/main/install.sh | bash
```

Remote one-command install and bootstrap a project:

```bash
curl -fsSL https://raw.githubusercontent.com/emosamastudio/agent-governance-standard/main/install.sh | bash -s -- --project /path/to/project
```

Local install from a checked-out repository:

```bash
./install.sh
```

Local install and bootstrap a project:

```bash
./install.sh --project /path/to/project
```

Install only one adapter:

```bash
./install.sh --adapter claude-code --project /path/to/project
./install.sh --adapter copilot-cli --project /path/to/project
```

Pin a tag or branch during remote install:

```bash
AGENT_GOVERNANCE_STANDARD_REF=v1.0.0 \
curl -fsSL https://raw.githubusercontent.com/emosamastudio/agent-governance-standard/main/install.sh | bash -s -- --project /path/to/project
```

## Resulting layers

### Shared core

- `~/.agent-governance-standard/`
- project `.agent-governance/`

### Claude Code adapter

- `~/.claude/CLAUDE.md`
- `~/.claude/settings.json`
- `~/.claude/bin/claude-governed`
- `~/.claude/bin/claude-governance-doctor`
- `~/.claude/bin/claude-governance-uninstall`
- project `CLAUDE.md`
- project `.claude/settings.json`
- project `.claude/hooks/*.py`
- project `.claude/bin/drift-check`

### Copilot CLI adapter

- `~/.copilot/copilot-instructions.md`
- `~/.copilot/bin/copilot-governed`
- `~/.copilot/bin/copilot-governance-doctor`
- `~/.copilot/bin/copilot-governance-uninstall`
- project `.github/copilot-instructions.md`
- project `.github/instructions/*.instructions.md`

## Shared project surface

Both adapters point at the same project governance state:

```text
.agent-governance/
  rules/
  state/
    delivery-intent.md
    current-mainline.md
    sidelines.md
    git-workflow.md
    lifecycle/
```

This gives different runtimes one common operating model instead of duplicating project truth.

## Governance added beyond baseline task planning

The standard also governs:

- **Delivery intent first**: before project planning and technology selection, explicitly confirm whether the user wants a final-system build or a fast MVP.
- **Commit-as-process-record**: commits should preserve planning, design, implementation, and cleanup milestones.
- **Branch and merge workflow**: protected branches, working branch naming, push discipline, PR discipline, and merge policy are tracked in shared state.
- **Hook hardening**: when a runtime supports hooks, hooks should actively enforce governance instead of only collecting logs.

In Claude Code, this is implemented with:

- user-level settings baseline
- lifecycle logging hooks
- prompt-submission gating
- permission-request gating
- config-change protection
- delegation gate hooks
- git governance hooks
- completion gates
- compaction gates and re-anchoring
- drift checks against shared project state

In Copilot CLI, this is implemented with:

- governed wrapper with explicit `--allow-tool` and `--deny-tool` baseline
- global Copilot instructions
- repository Copilot instructions
- modular `.github/instructions/*.instructions.md` workflow packs
- shared `.agent-governance/` state
- doctor and uninstall tools

## Claude strongest-mode maintenance

After installing the Claude adapter, use:

```bash
~/.claude/bin/claude-governed
~/.claude/bin/claude-governance-doctor
~/.claude/bin/claude-governance-doctor --project /path/to/project
~/.claude/bin/claude-governance-uninstall --project /path/to/project
```

Notes:

- `claude-governed` is still the strongest entrypoint because it uses `--append-system-prompt-file`.
- Plain `claude` is also strengthened through `~/.claude/CLAUDE.md` and `~/.claude/settings.json`.
- Re-running `./install.sh` acts as the upgrade path.

## Copilot strongest-mode maintenance

After installing the Copilot adapter, use:

```bash
~/.copilot/bin/copilot-governed
~/.copilot/bin/copilot-governance-doctor
~/.copilot/bin/copilot-governance-doctor --project /path/to/project
~/.copilot/bin/copilot-governance-uninstall --project /path/to/project
```

Notes:

- `copilot-governed` is the strongest entrypoint because it applies an explicit tool permission baseline with `--allow-tool` and `--deny-tool`.
- Copilot strongest mode relies on layered instructions plus the governed wrapper, since Copilot CLI does not expose Claude-style lifecycle hooks.
- Re-running `./install.sh` acts as the upgrade path.

## Why “user-level top-level constraints”

This is the cross-project, always-on constraint layer for one human operator.
It is not project-specific business context. It defines how the agent should work everywhere:

- planning before parallelism
- mainline before sidelines
- acceptance before completion
- cognition checks before stack lock-in
- governance, logs, hooks, and review as part of the system

## Notes

- Existing runtime config files are preserved and updated with managed blocks when possible.
- Claude gets stronger enforcement through a wrapper that appends the top-level constraints as a system prompt addition.
- Copilot uses its native instruction hierarchy: global instructions, repository instructions, and modular `.github/instructions/*.instructions.md`.
- Runtimes without hooks still use the shared governance surface, but hook hardening is strongest on runtimes that actually support lifecycle hooks.
