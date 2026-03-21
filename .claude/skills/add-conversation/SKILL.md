---
name: add-conversation
description: "Add important conversation context as a reference document"
argument-hint: "<topic>"
---

# /add-conversation — Save Conversation Context

Save important decisions, discussions, or context from the current conversation as a reference document for future sessions.

### Workflow
1. Identify the key decisions, insights, or context worth preserving
2. Summarize in a structured format
3. Save to `.claude/reference/conversations/[topic]-[date].md`
4. Update `.claude/reference/README.md` index

### Format
```markdown
# Conversation: [Topic]

**Date**: YYYY-MM-DD
**Participants**: user, agents involved

## Context
What was being discussed and why.

## Decisions Made
1. Decision — rationale

## Key Insights
- Insight 1
- Insight 2

## Impact on Project
How this affects future work.
```

### Rules
- Only save non-obvious decisions and context
- Don't save things derivable from code or git history
- Keep it concise — future readers need signal, not noise
