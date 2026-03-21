---
name: api-design
description: "Design RESTful API endpoints with contracts and documentation"
argument-hint: "<resource or feature>"
disable-model-invocation: true
context:
  - docs/templates/CONTEXT-TEMPLATE.md
  - PROJECT.md
---

# /api-design — API Design (Domain Skill)

Auto-loaded when working with API-related tasks.

### Guidelines
- RESTful conventions: proper HTTP methods, status codes, resource naming
- Consistent response format:
  ```json
  { "data": {...}, "meta": {...}, "errors": [...] }
  ```
- Pagination: cursor-based for large collections
- Versioning: URL path (`/v1/`) or header
- Authentication: Bearer tokens, API keys in headers (never query params)
- Rate limiting: return `429` with `Retry-After` header
- HATEOAS links where appropriate

### Endpoint Template
```
METHOD /api/v1/resource
Auth: required/optional/none
Rate limit: N req/min

Request:
  Headers: { Authorization: "Bearer <token>" }
  Body: { field: type (required|optional) }

Response 200:
  { "data": { ... }, "meta": { "total": N } }

Response 400:
  { "errors": [{ "code": "VALIDATION_ERROR", "field": "name", "message": "..." }] }

Response 401:
  { "errors": [{ "code": "UNAUTHORIZED" }] }
```

### Checklist
- [ ] Resource naming is plural nouns (`/users`, not `/user`)
- [ ] HTTP methods match CRUD semantics
- [ ] Error responses include actionable messages
- [ ] Sensitive data never in URL query parameters
- [ ] Pagination for list endpoints
