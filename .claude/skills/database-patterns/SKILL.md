---
name: database-patterns
description: "Database design patterns — schema, queries, indexing, migrations"
disable-model-invocation: true
context:
  - PROJECT.md
---

# /database-patterns — Database Design (Domain Skill)

Auto-loaded when working with database-related tasks.

### Schema Design
- Normalize to 3NF, denormalize only with measured justification
- Every table has: `id` (PK), `created_at`, `updated_at`
- Use UUIDs for public-facing IDs, integers for internal
- Foreign keys with appropriate ON DELETE behavior
- Soft deletes (`deleted_at`) for user-facing data

### Indexing
- Index all foreign keys
- Index frequently queried columns
- Composite indexes: most selective column first
- Partial indexes for filtered queries
- Monitor query plans — don't over-index

### Query Patterns
- Avoid N+1: use JOINs or batch loading
- Paginate large result sets (cursor > offset for large tables)
- Use transactions for multi-step mutations
- Prepared statements — never string-concatenate SQL

### Migration Rules
- Always include up AND down migrations
- Never drop columns in production without deprecation period
- Add columns as nullable first, backfill, then add constraints
- Test migrations against production-size data
