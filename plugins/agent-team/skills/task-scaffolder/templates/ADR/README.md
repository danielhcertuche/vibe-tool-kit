<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/ADR
-->

# ADR Template: {{NAME}}

Architecture Decision Record for `{{NAME}}`.

## Owner

`{{OWNER_AGENT}}`

## Lifecycle

```
Proposed → Accepted → (Deprecated | Superseded)
```

## Naming convention

File: `ADR-NNN-{{NAME}}.md` where NNN is the next sequential number in `docs/adr/`.

## Usage

1. Copy `skeleton.md` to `docs/adr/ADR-NNN-{{NAME}}.md`
2. Fill all sections — do not leave `—` placeholders in accepted ADRs
3. Update Status to `Accepted` once reviewed
4. Link from `CLAUDE.md` or `docs/architecture.md` if it affects the whole repo
