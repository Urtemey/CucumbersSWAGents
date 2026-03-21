---
name: self-improve
description: "Karpathy loop: iteratively improve a skill using eval assertions"
argument-hint: "<skill-name>"
---

# /self-improve — Karpathy Self-Improvement Loop

### Step 1: Load
- Read `.claude/skills/<skill-name>/SKILL.md`
- Read `.claude/skills/<skill-name>/eval.json` (if missing, run `/generate-eval` first)

### Step 2: Evaluate
- Run ALL test cases from eval.json
- Execute skill with each test input
- Evaluate output against binary assertions (pass/fail)
- Score = passed / total assertions × 100

### Step 3: Decide
- Score improved → commit SKILL.md change
- Score declined → revert to best version
- Score = 100 → done

### Step 4: Tweak
- Analyze which assertions failed
- Make exactly ONE targeted change to SKILL.md

### Step 5: Loop
- Back to Step 2
- Max 10 iterations or until perfect score
- Stop if no progress after 3 consecutive iterations

### Step 6: Report
```
## Self-Improvement Report: <skill-name>
- Starting Score: X%
- Final Score: Y%
- Iterations: N
- Changes Made: list
- Remaining Failures: list (if any)
```

## Rules
- NEVER change eval.json — it's ground truth
- ONE change per iteration
- Commit improvements, revert regressions
