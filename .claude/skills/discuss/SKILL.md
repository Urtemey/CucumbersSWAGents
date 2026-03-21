---
name: discuss
description: "Structured technical discussion — explore trade-offs before deciding"
argument-hint: "<topic or question>"
---

# /discuss — Technical Discussion

Explore a technical question without committing to implementation.

### Workflow
1. Understand the question or dilemma
2. Research relevant code, docs, and patterns
3. Present at least 2-3 options with trade-offs:
   ```
   ## Option A: [Name]
   - Pros: ...
   - Cons: ...
   - Effort: Low/Med/High
   - Risk: Low/Med/High

   ## Option B: [Name]
   - Pros: ...
   - Cons: ...
   ```
4. Give a recommendation with rationale
5. Ask the user for their preference before proceeding

### Rules
- No code changes — discussion only
- Always present multiple options
- Be honest about trade-offs and unknowns
- Consider existing architecture and constraints
