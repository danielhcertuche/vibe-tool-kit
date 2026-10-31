<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/model
-->

# Model Card: {{NAME}}

## Model details

| Field | Value |
|-------|-------|
| Owner | `{{OWNER_AGENT}}` |
| Created | {{CREATED_AT}} |
| Framework | — |
| Algorithm | — |

## Intended use

- **Primary use:** —
- **Out-of-scope:** —

## Data

- **Training source:** `{{UPSTREAM}}`
- **Validation split:** —
- **Feature count:** —

## Metrics

| Metric | Dev | Prod |
|--------|-----|------|
| — | — | — |

## Limitations and risks

- —

## Evaluation procedure

```bash
python -c "from {{NAME}}.skeleton import {{NAME}}Model; m = {{NAME}}Model(); m.evaluate(X_test, y_test)"
```
