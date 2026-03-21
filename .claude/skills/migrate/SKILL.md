---
name: migrate
description: "Generate and run database or schema migrations"
argument-hint: "<migration description>"
---

# /migrate — Migration Management

### Workflow
1. Understand the schema change needed
2. Check current migration state
3. Generate migration file with:
   - Up migration (apply change)
   - Down migration (rollback change)
4. Review migration with user
5. Run migration in dev environment
6. Verify data integrity
7. Update data model docs

### Rules
- Always include rollback (down migration)
- Never drop columns/tables without explicit approval
- Test migration on copy of data first
- Back up before destructive migrations
