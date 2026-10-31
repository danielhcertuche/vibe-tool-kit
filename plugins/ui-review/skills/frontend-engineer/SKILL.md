---
name: frontend-engineer
description: Frontend engineering playbook for building performant, accessible, and resilient UIs. Use for component architecture, state and data management, web vitals optimization, client-side security hardening, and frontend observability.
---

# Frontend Engineer

## Scope

Use when implementing UI features, optimizing performance, hardening client-side security, improving accessibility, or increasing test coverage for frontend code.

## Workflow

1. **Map boundaries first**: Identify affected routes, components, state slices, and API contracts before writing any code.
2. **Component contract**: Define props, events, and exposed behavior. Align with the design system before implementation.
3. **State and data strategy**: Choose fetching and caching approach (React Query/SWR, Apollo/GraphQL, Zustand/Redux). Handle loading, error, empty, and stale states explicitly — always.
4. **Optimistic UI and resilience**: Apply optimistic updates where latency matters. Handle network failures and partial data gracefully.
5. **Performance budget**: Measure Web Vitals (LCP, CLS, INP) before and after changes. Flag bundle additions > 50KB uncompressed to `tech-lead`.
6. **Client-side security**: Sanitize all user-controlled content. No inline scripts. Apply CSP. Store tokens only in httpOnly cookies or memory — never localStorage.
7. **Test and validate**: Unit tests for logic, integration tests for user flows, a11y assertions in component tests.

## Design → Code (Pencil MCP: `pencil`)

When there are `.pen` design files in the repo, use Pencil MCP tools to read designs and implement them faithfully — same text, icons, spacing, and colors as the design.

### Pencil tools for frontend implementation

| Tool | When to use |
|------|-------------|
| `get_editor_state` | Call at start to understand the document structure and canvas state. |
| `batch_get` | Read the content of `.pen` files to inspect frames, components, and layout. |
| `search_design_nodes` | Find all components in the design system to understand what's already available. |
| `get_variables` | Read design tokens (color palette, spacing, typography scale) before coding. |
| `get_guidelines(topic=code)` | Get coding guidelines for translating `.pen` designs to code. Call once per session. |
| `get_guidelines(topic=tailwind)` | When the project uses Tailwind CSS. |
| `get_screenshot(nodeId)` | Get a visual reference of any frame or component to compare with your implementation. |
| `open_document(filePath)` | Open a specific `.pen` file. Example: `"designs/components.pen"`. |

### Design-to-Code rules

1. **Read design tokens first**: Call `get_variables` before any implementation. Use the token values for colors, spacing, radii — never hardcode hex values.
2. **Match exactly**: Same text labels, icon names, spacing, and layout as the design. Do not improvise.
3. **Reuse existing code**: Before implementing a component, search the codebase for an existing implementation. Translate `.pen` components to existing code components when a match exists.
4. **Use the project's styling system**: If using Tailwind, apply Tailwind classes. If using CSS modules, CSS modules. Use the correct version of libraries already in the project.
5. **Do not create documentation**: When generating code from design, don't add JSDoc, READMEs, or changelogs.
6. **Visual validation**: Use `get_screenshot` to get a reference image, then compare your implementation visually. Flag discrepancies as review comments.

### Design-to-Code workflow

```
1. open_document("designs/feature.pen")
2. get_guidelines(topic="code")          ← load coding rules once
3. get_variables                         ← extract design tokens
4. search_design_nodes                   ← find components and frames
5. batch_get(nodeIds)                    ← read specific frame content
6. get_screenshot(nodeId)                ← get visual reference
7. implement in code using existing project patterns
8. compare screenshot with implementation, iterate
```

## Toolbelt (via Bash)

- **Build/lint**: `npm run build`, `tsc --noEmit`, `eslint`, `biome check`
- **Test**: `vitest run`, `jest --coverage`, `playwright test`, `cypress run`
- **Performance**: `lighthouse --output=json --quiet`, `npx bundlesize`, `npx source-map-explorer dist/`
- **A11y**: `axe-core` in test suite, `playwright` accessibility assertions
- **API contracts**: `npx openapi-generator-cli generate`, OpenAPI diff tools
- **Deps**: `npm audit`, `depcheck`
- **Design**: Pencil MCP (`pencil` server) for reading `.pen` design files

## Web Vitals Targets (Core)

| Metric | Good | Needs Work |
|--------|------|------------|
| LCP (Largest Contentful Paint) | ≤ 2.5s | > 4.0s |
| CLS (Cumulative Layout Shift) | ≤ 0.1 | > 0.25 |
| INP (Interaction to Next Paint) | ≤ 200ms | > 500ms |

## Security Checklist

- Never `dangerouslySetInnerHTML` from untrusted input
- Tokens: httpOnly cookies only (no localStorage, no sessionStorage for sensitive data)
- CSP headers configured and tested
- All user input sanitized before render or API submission
- No hardcoded secrets or API keys in frontend code

## Brand Compliance — Fashion AI (MANDATORY)

All UI outputs MUST follow the Fashion AI brand system:
1. Call `brand_graph_query(action="resolve", query="usecase.<type>")` to get applicable rules, tokens, and assets.
2. Use ONLY tokens from `get_design_tokens()` for colors and typography in CSS/styles.
3. After implementing, call `validate_design_spec(design_spec=..., strict=true)` — do NOT merge if verdict is `FAIL`.

## Referencia de diseño base — skill `corporate`

Antes de proponer tokens, componentes o layout, revisar `~/.agents/skills/corporate/`
(SKILL.md: estados obligatorios, WCAG 2.2 AA verificable, anti-patrones, checklist QA;
DESIGN.md: tokens de referencia). **Precedencia:** el design system del proyecto
(el design system del proyecto (parámetro `DESIGN_SYSTEM`)) manda;
los tokens de la skill son fallback solo si el repo no tiene los suyos. El proceso y la
checklist aplican siempre. Regla cross-IDE: `~/.agents/CORE.md` §9.

## Guardrails

- Do not fetch data without explicitly handling loading, error, and empty states.
- A11y is baseline: WCAG AA — keyboard navigation, focus management, ARIA, contrast.
- Bundle size regressions > 50KB require `tech-lead` review before merge.
- XSS: zero tolerance for unescaped user content in DOM.
- Contract changes with backend require coordination before implementation.

## Handoff Notes

- To `backend-engineer`: API contract gaps, missing endpoints, response shape mismatches.
- To `product-designer`: UX edge cases discovered during implementation, responsive constraints.
- To `qa-automation`: component interaction scenarios, error states to test, a11y assertions.
- To `security-appsec`: client-side auth flows, token handling patterns, any dynamic injection.
