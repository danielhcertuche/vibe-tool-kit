<!-- artifact metadata
owner_agent: {{OWNER_AGENT}}
upstream:    {{UPSTREAM}}
downstream:  {{DOWNSTREAM}}
created_at:  {{CREATED_AT}}
template:    task-scaffolder/component
-->

# {{NAME}} Component

React component for `{{NAME}}`.

## Owner

`{{OWNER_AGENT}}`

## Usage

```tsx
import { {{NAME}} } from "./{{NAME}}";

<{{NAME}} className="my-class" />
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `className` | `string` | `undefined` | CSS class override |

## Tests

```bash
npx vitest run {{NAME}}.test.tsx
```
