---
name: node-backend
description: "Node.js backend patterns and conventions"
disable-model-invocation: true
context:
  - PROJECT.md
---

# /node-backend — Node.js Backend Patterns (Domain Skill)

### Project Structure
```
src/
  config/       — Environment, database, external service config
  middleware/   — Auth, validation, error handling, logging
  routes/       — Route definitions
  controllers/  — Request handling (thin — delegate to services)
  services/     — Business logic (testable, framework-agnostic)
  models/       — Data models / ORM entities
  utils/        — Pure utility functions
  types/        — TypeScript types and interfaces
```

### Error Handling
- Custom error classes extending `Error`
- Global error handler middleware (catch-all)
- Operational vs programming errors — handle differently
- Never swallow errors — log with context
- Return consistent error response format

### Security
- Helmet for HTTP headers
- CORS configuration (whitelist, not `*`)
- Rate limiting on public endpoints
- Input validation (zod, joi, class-validator)
- SQL injection prevention (parameterized queries)
- XSS prevention (sanitize output)

### Patterns
- **Service Layer** — Business logic isolated from HTTP
- **Repository Pattern** — Data access abstraction
- **Middleware Chain** — Auth → Validate → Handle → Respond
- **Dependency Injection** — Constructor injection for testability
- **Graceful Shutdown** — Handle SIGTERM, close connections
