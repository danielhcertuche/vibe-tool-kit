<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/endpoint
-->

# {{NAME}} Endpoint

FastAPI router for `{{NAME}}` resource.

## Owner

`{{OWNER_AGENT}}`

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/{{NAME}}/` | List resources |
| POST | `/{{NAME}}/` | Create resource |

## Mount in app

```python
from {{NAME}}.skeleton import router
app.include_router(router)
```

## Tests

```bash
pytest test_{{NAME}}.py -v
```
