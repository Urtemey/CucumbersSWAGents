---
name: react-patterns
description: "React development patterns and best practices"
disable-model-invocation: true
context:
  - PROJECT.md
---

# /react-patterns — React Patterns (Domain Skill)

### Component Design
- Prefer function components with hooks
- Single responsibility — one component, one purpose
- Composition over inheritance
- Props for configuration, context for cross-cutting concerns
- Keep components under 150 lines

### State Management
- Local state: `useState` for component-specific state
- Shared state: Context or state management library
- Server state: React Query / SWR (not manual useEffect)
- Avoid prop drilling — use composition or context

### Performance
- `React.memo` only after measuring (premature optimization hurts)
- `useMemo`/`useCallback` for expensive computations or stable references
- Virtualize long lists (react-window, react-virtuoso)
- Code split with `React.lazy` + Suspense
- Avoid inline object/array creation in JSX

### Patterns
- **Container/Presentational** — Separate data fetching from rendering
- **Custom Hooks** — Extract reusable logic (useAuth, useDebounce)
- **Compound Components** — Related components that share state
- **Render Props / Children as Function** — Flexible composition

### Anti-Patterns to Avoid
- `useEffect` for derived state (use `useMemo` instead)
- State for values computable from props
- Giant monolithic components
- Direct DOM manipulation (use refs)
- Nested ternaries in JSX
