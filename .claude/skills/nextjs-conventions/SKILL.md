---
name: nextjs-conventions
description: "Next.js project conventions and patterns"
disable-model-invocation: true
context:
  - PROJECT.md
---

# /nextjs-conventions — Next.js Patterns (Domain Skill)

### App Router Conventions
- `page.tsx` — Route page component
- `layout.tsx` — Shared layout (wraps children)
- `loading.tsx` — Loading UI (Suspense boundary)
- `error.tsx` — Error boundary
- `not-found.tsx` — 404 page
- Route groups: `(group)/` for organization without URL impact
- Parallel routes: `@slot/` for simultaneous rendering

### Data Fetching
- Server Components by default — fetch data on the server
- `"use client"` only when needed (interactivity, hooks, browser APIs)
- Use `fetch` with Next.js caching: `{ cache: 'force-cache' | 'no-store' }`
- Revalidate: `{ next: { revalidate: 3600 } }` for ISR
- Server Actions for mutations (form submissions, data updates)

### Performance
- Use `<Image>` for automatic optimization
- Use `<Link>` for client-side navigation
- Dynamic imports for heavy components
- Metadata API for SEO (`generateMetadata`)
- Route segment config for caching control

### File Organization
```
app/
  (auth)/
    login/page.tsx
    register/page.tsx
  (dashboard)/
    layout.tsx
    page.tsx
    settings/page.tsx
  api/
    route.ts
components/
  ui/          — Reusable UI components
  features/    — Feature-specific components
lib/           — Utilities, API clients, helpers
```
