<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/model
-->

# {{NAME}} Model

ML model class for `{{NAME}}`.

## Owner

`{{OWNER_AGENT}}`

## Methods to implement

| Method | Signature | Description |
|--------|-----------|-------------|
| `train` | `(X, y) → None` | Fit on training data from `{{UPSTREAM}}` |
| `predict` | `(X) → ndarray` | Inference; raises if not trained |
| `evaluate` | `(X, y) → dict[str, float]` | Returns metric dict (e.g. `{"rmse": 0.1}`) |

## Files

| File | Purpose |
|------|---------|
| `skeleton.py` | Model class |
| `model_card.md` | Intended use, metrics, limitations |

## Tests

```bash
pytest test_{{NAME}}.py -v
```
