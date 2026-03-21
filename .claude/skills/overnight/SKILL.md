---
name: overnight
description: "Batch self-improve all skills autonomously"
argument-hint: "[--target-score N] [--max-skills M]"
---

# /overnight — Batch Self-Improvement

Runs unattended. Improves all skills below target score.

1. Scan all skills in `.claude/skills/`
2. Read metrics, sort by score (worst first)
3. Generate missing evals via `/generate-eval`
4. Run `/self-improve` on each skill below target (default: 80)
5. Save report to `.claude/hooks/logs/overnight-report-YYYY-MM-DD.md`
