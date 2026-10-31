<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/migration
-->

# Migration: {{NAME}}

SQL Server migration for `{{NAME}}`.

## Owner

`{{OWNER_AGENT}}`

## Apply

```bash
sqlcmd -S <server> -d <database> -i skeleton.sql
```

## Rollback

```bash
sqlcmd -S <server> -d <database> -i rollback.sql
```

## Safety checklist

- [ ] Migration is idempotent (guarded with `IF NOT EXISTS`)
- [ ] Rollback tested in dev before applying to prod
- [ ] Reviewed by DBA for index and locking implications
- [ ] Backup taken before applying to prod
