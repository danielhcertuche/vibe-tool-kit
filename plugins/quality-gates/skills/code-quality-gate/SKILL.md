---
name: code-quality-gate
description: Transversal quality gate for all code artifacts. Runs language-specific linters, formatters, type checkers, and tests before any deliverable is marked as ready. Supports Python (ruff + mypy + pytest), SQL (sqlfluff), TypeScript (prettier + tsc + vitest), notebooks (nbqa), and Terraform (fmt + validate). Graceful degradation when tools are missing.
---

# Code Quality Gate

## Scope

Use this skill **before any agent marks a code deliverable as ready**. Applies to every agent that produces code. Run it also when the user asks to review or validate a file.

Trigger conditions:
1. Agent finished implementing a code artifact
2. Agent is about to hand off to another agent
3. User asks for code review or validation
4. Pre-merge or pre-deploy check requested

## Languages Covered

| Language | Check Script | Tools |
|----------|-------------|-------|
| Python (`py`) | `scripts/checks/python.sh` | ruff, mypy, pytest |
| SQL | `scripts/checks/sql.sh` | sqlfluff |
| TypeScript / TSX | `scripts/checks/ts.sh` | prettier, tsc, vitest |
| Notebooks (`ipynb`) | `scripts/checks/notebook.sh` | nbqa ruff |
| Terraform (`tf`) | `scripts/checks/terraform.sh` | terraform |

## Workflow

1. **Invoke the gate** via the entry point:
   ```bash
   bash "${HOME}/.claude/skills/code-quality-gate/scripts/run-gate.sh" <path>
   ```
   Default path is `.` (repo root). Pass a specific directory or file for scoped checks.
   The skill is installed globally at `~/.claude/skills/code-quality-gate/` — works from any repo.

2. **The gate auto-detects** which languages are present and runs only relevant scripts.

3. **Read the JSON output** from stdout. The agent must not mark a task done if `status` is `"fail"`.

4. **For failures**: read `findings` array, fix issues, re-run gate, confirm `"pass"`.

## Output Contract

Gate outputs JSON to stdout:

```json
{
  "gate": "code-quality-gate",
  "status": "pass|fail",
  "checks": [
    {
      "check": "python|sql|ts|notebook|terraform",
      "status": "pass|fail|skip",
      "findings": 0,
      "details": []
    }
  ],
  "timestamp": "2024-01-01T00:00:00Z"
}
```

- `status: "pass"` — all checks passed or skipped (missing tools)
- `status: "fail"` — one or more checks found issues
- `status: "skip"` — tool not installed; `details` contains install instructions

Human-readable summary goes to stderr.

## Per-Language Checklists

### Python
- [ ] All public functions have type annotations on parameters and return value
- [ ] No `print()` in production modules (use `logging`)
- [ ] `ruff check` exits 0
- [ ] `ruff format --check` exits 0
- [ ] `mypy` exits 0 (or all errors suppressed with justification)
- [ ] `pytest` passes if test files exist nearby

### SQL
- [ ] No bare `SELECT *` in non-exploratory queries
- [ ] Exploration queries have an explicit `LIMIT`
- [ ] CTEs are named descriptively (no `cte1`, `tmp`, `t`)
- [ ] No dynamic SQL built from string concatenation
- [ ] `sqlfluff lint` exits 0

### TypeScript / TSX
- [ ] `prettier --check` exits 0
- [ ] `tsc --noEmit` exits 0
- [ ] No unconstrained `any` in production code (test files allowed)
- [ ] `vitest run` passes if test files exist nearby

### Notebooks
- [ ] Cells are idempotent (safe to re-run in order)
- [ ] No hardcoded credentials or tokens
- [ ] No cell outputs >100 KB
- [ ] `nbqa ruff` exits 0 on notebook cells

### Terraform
- [ ] `terraform fmt -check` exits 0
- [ ] `terraform validate` exits 0

## Graceful Degradation

If a tool is not installed, the check script MUST:
- Print `[SKIP] <tool> not found — install: <command>` to stderr
- Output `{"check": "<name>", "status": "skip", "findings": 0, "details": ["tool-missing: <tool>"]}` to stdout
- Exit 0 (missing tools do NOT block the gate)

Missing tools are surfaced as informational findings — the agent should note them but not fail the delivery.

## Entry Point

```bash
bash "${HOME}/.claude/skills/code-quality-gate/scripts/run-gate.sh" [path] [--lang=python,sql,ts,notebook,terraform]
```

- `path` — directory or file to scan (default: `.`)
- `--lang=` — optional comma-separated language filter (default: auto-detect)
