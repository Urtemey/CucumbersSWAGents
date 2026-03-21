---
name: no-coauthor-in-commits
description: "User does not want Claude listed as co-author in git commits"
type: feedback
---

Do not add `Co-Authored-By: Claude ...` to commit messages.

**Why:** User explicitly removed it when committing.
**How to apply:** When creating git commits, never include co-author attribution lines.
