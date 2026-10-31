---
name: agent-team-core
description: Shared multi-agent operating protocol for keeping task packets, handoffs, scope, and validation aligned across Copilot, Claude Code, and Codex.
---

Use this skill when the task involves more than one role, has multiple phases, or can drift because the user request is broad.

Rules:
- Start with a task packet before proposing or changing code.
- Keep one owner per file/module at a time.
- Restate the packet if scope or constraints change.
- Use explicit handoffs instead of implicit "done" statements.
- Do not drop validation. If it could not run, say so.

Task packet:
```text
Objective:
Scope:
Constraints:
Files/areas:
Validation:
Open questions:
```

Handoff:
```text
Status:
Decisions:
Files touched:
Validation:
Risks/blockers:
Next action / owner:
```

Escalation:
- Architecture or sequencing ambiguity -> `tech-lead`
- Backend ownership -> `backend-engineer`
- Frontend ownership -> `frontend-engineer`
- Regression coverage -> `qa-automation`
- Security exposure -> `security-appsec`
