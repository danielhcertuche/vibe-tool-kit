<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/dashboard
-->

# {{NAME}} Dashboard

Dashboard page with KPI row + main chart + detail table.

## Owner

`{{OWNER_AGENT}}`

## Layout

```
┌─────────────────────────────────┐
│  KPI 1    KPI 2    KPI 3        │  ← flex row
├─────────────────────────────────┤
│  Main chart ({{UPSTREAM}})      │
├─────────────────────────────────┤
│  Detail table                   │
└─────────────────────────────────┘
```

## Usage

```tsx
import { {{NAME}}Dashboard } from "./{{NAME}}Dashboard";

<{{NAME}}Dashboard className="my-dashboard" />
```

## Tests

```bash
npx vitest run {{NAME}}Dashboard.test.tsx
```
