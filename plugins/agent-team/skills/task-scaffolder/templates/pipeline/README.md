<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/pipeline
-->

# {{NAME}} Pipeline

ETL pipeline moving data from `{{UPSTREAM}}` to `{{DOWNSTREAM}}`.

## Owner

`{{OWNER_AGENT}}`

## Usage

```python
from {{NAME}} import {{NAME}}Pipeline

pipeline = {{NAME}}Pipeline()
rows_loaded = pipeline.run()
```

## Methods to implement

| Method | Description |
|--------|-------------|
| `extract()` | Pull raw records from `{{UPSTREAM}}` |
| `transform(records)` | Apply business rules and transformations |
| `load(records)` | Write to `{{DOWNSTREAM}}`, return row count |

## Tests

```bash
pytest test_{{NAME}}.py -v
```
