---
name: task-scaffolder
description: Bootstrap any artifact (pipeline, endpoint, component, migration, notebook, model, ADR, dashboard) from a typed skeleton with lineage metadata. Run code-quality-gate after scaffolding.
---

# task-scaffolder

Bootstrap new artifacts from validated skeletons. Every skeleton carries lineage metadata and passes code-quality-gate before handoff.

## Trigger

Invoke when **any agent starts a new artifact from scratch** — file does not yet exist, or the existing stub lacks structure.

## Input contract

```json
{
  "template":     "pipeline|endpoint|component|migration|notebook|model|ADR|dashboard",
  "name":         "snake_case_artifact_name",
  "target_path":  "relative/path/to/place/artifact/",
  "owner_agent":  "agent-name-as-in-agent_army",
  "upstream":     ["source_table_or_service"],
  "downstream":   ["consumer_table_or_service"]
}
```

## Workflow

1. **Identify template** from `template` field.
2. **Copy skeleton files** from `~/.claude/skills/task-scaffolder/templates/<type>/` to `target_path`.
   (Skill installed globally — works from any repo.)
3. **Replace placeholders** (see table below) — every occurrence, every file.
4. **Run code-quality-gate** on `target_path` — fix any issues before declaring done.
5. **Report** files created and gate result.

## Placeholders

| Placeholder | Replaced with |
|---|---|
| `{{NAME}}` | `name` from input (snake_case) |
| `{{OWNER_AGENT}}` | `owner_agent` from input |
| `{{CREATED_AT}}` | ISO-8601 date (YYYY-MM-DD) at scaffolding time |
| `{{UPSTREAM}}` | `upstream` list, comma-separated |
| `{{DOWNSTREAM}}` | `downstream` list, comma-separated |

## Templates

| Template | Skeleton files | Best for |
|---|---|---|
| `pipeline` | `skeleton.py`, `test_skeleton.py`, `README.md` | ETL/ELT pipelines, data materialization |
| `endpoint` | `skeleton.py`, `test_skeleton.py`, `README.md` | FastAPI routers, REST endpoints |
| `component` | `skeleton.tsx`, `skeleton.test.tsx`, `README.md` | React UI components |
| `migration` | `skeleton.sql`, `rollback.sql`, `README.md` | Database schema changes |
| `notebook` | `skeleton.ipynb`, `README.md` | Exploratory analysis, ML experiments |
| `model` | `skeleton.py`, `model_card.md`, `README.md` | ML model classes |
| `ADR` | `skeleton.md`, `README.md` | Architecture decision records |
| `dashboard` | `skeleton.tsx`, `skeleton.test.tsx`, `README.md` | Dashboard pages with layout grid |

## Metadata block (every skeleton file)

Every skeleton file begins with this block (adapted to language comment syntax):

```
# --- artifact metadata ---
# owner_agent: {{OWNER_AGENT}}
# upstream:    {{UPSTREAM}}
# downstream:  {{DOWNSTREAM}}
# created_at:  {{CREATED_AT}}
# template:    task-scaffolder/{{TEMPLATE_TYPE}}
# ---
```

For non-Python files, use the appropriate comment syntax:
- SQL: `-- ---`
- TypeScript/TSX: `// ---`
- Markdown: `<!-- --- -->`
- Jupyter: metadata cell (raw or markdown)

## Graceful rules

- If `target_path` already has files: warn but do NOT overwrite unless the user confirms.
- If a placeholder is missing from input: leave `{{PLACEHOLDER}}` in place and log a warning.
- Always run code-quality-gate last; surface any findings before marking task done.
