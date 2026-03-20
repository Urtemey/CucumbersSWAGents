# /validation/system-review — Process Improvement Analysis

> **NOTE:** This is NOT a code review. This reviews the development PROCESS itself and suggests improvements to Agent.md, command templates, and skill definitions.

## Instructions

### Step 1: Gather Data
1. Read recent execution reports from `docs/` (if any).
2. Review git history for patterns: commit frequency, branch naming, PR flow.
3. Check if `Agent.md` rules were followed consistently.
4. Review command/skill usage patterns (from hook logs if available).

### Step 2: Analyze Process
For each divergence or issue found:
- **Classify**: Justified adaptation vs. Problematic deviation
- **Impact**: How did it affect quality, speed, or correctness?
- **Root cause**: Was it unclear instructions, missing guardrails, or an edge case?

### Step 3: Recommend Updates

```markdown
## System Review Report

**Date**: YYYY-MM-DD
**Scope**: [what period/work was reviewed]

### Process Health
- Plan adherence: X%
- Validation pass rate: Y%
- Average iterations to completion: N

### Divergences Found
1. **[Justified]** Description — no action needed
2. **[Problematic]** Description — needs fix

### Recommended Updates

#### Agent.md
- [ ] Section N: suggested change and why

#### Commands
- [ ] command-name: suggested change and why

#### Skills
- [ ] skill-name: suggested change and why

#### Workflow
- [ ] Process change suggestion and why

### Priority Actions
1. Highest priority improvement
2. Second priority improvement
3. Third priority improvement
```

### Step 4: Offer to Apply
Ask the user if they want to apply any of the recommended changes automatically.
