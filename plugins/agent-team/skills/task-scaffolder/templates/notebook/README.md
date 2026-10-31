<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/notebook
-->

# {{NAME}} Notebook

Exploratory analysis notebook for `{{NAME}}`.

## Owner

`{{OWNER_AGENT}}`

## Structure

| Section | Purpose |
|---------|---------|
| 1. Load data | Ingest from `{{UPSTREAM}}` |
| 2. Analysis | Core exploration |
| 3. Conclusions | Key findings |

## Quality rules

- Cells must be idempotent (safe to re-run in order)
- No hardcoded credentials — use env vars or secret managers
- Clear outputs before committing (max 100 KB total output)
- Use `logging` instead of `print()` for diagnostic messages
