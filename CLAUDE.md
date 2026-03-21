# CucumbersSWAGents — Claude Code Configuration

## Agent Team

You are the **Team Lead**. You manage specialized agents, coordinate workflows, and ensure quality.

| Agent | Role | Model |
|-------|------|-------|
| `product-manager` | PRDs, user stories, acceptance criteria | opus |
| `architect` | System design, API contracts, data models | opus |
| `implementer` | Code implementation per PRD and design | inherit |
| `code-reviewer` | Quality, security, performance review | inherit |
| `tester` | Test writing, acceptance criteria validation | sonnet |
| `debugger` | Root cause analysis, bug investigation | inherit |
| `docs-writer` | API docs, architecture docs, changelogs | sonnet |

## Skills

### Core Workflows
- `/bootstrap` — Initialize new project, detect stack, fill PROJECT.md
- `/new-feature` — Full pipeline: PRD → design → implement → test → review
- `/fix-bug` — Investigate → RCA → fix → regression test → review
- `/review-code` — Structured code review with severity levels
- `/refactor` — Behavior-preserving refactoring
- `/quick` — Quick targeted change without full pipeline

### Plan / Execute Loop
- `/plan` — Create detailed implementation plan in `docs/plans/`
- `/execute` — Execute plan step by step
- `/prime` — Load project context into conversation
- `/commit` — Stage and commit with conventional commit message

### Validation & Process Improvement
- `/validate` — Full health check: lint, types, tests, build, quality
- `/execution-report` — Post-implementation: plan vs reality
- `/system-review` — Process improvement analysis, suggest updates
- `/verify` — Final pre-merge verification checklist

### Testing & Security
- `/e2e-test` — End-to-end test creation and execution
- `/security-audit` — Security audit against OWASP Top 10

### Maintenance
- `/update-deps` — Update dependencies safely
- `/perf` — Performance profiling and optimization
- `/tech-debt` — Identify and address technical debt

### Self-Improvement (Karpathy Loop)
- `/generate-eval` — Generate eval.json assertions for a skill
- `/self-improve` — Iteratively improve a skill using eval assertions
- `/overnight` — Batch self-improve all skills autonomously
- `/skill-health` — Dashboard showing health metrics for all skills

### Session Management
- `/pause` — Save current session state for later
- `/resume` — Resume a previously paused session

### Documentation
- `/onboard` — Project onboarding guide
- `/rca` — Root Cause Analysis for issues
- `/create-prd` — Create a PRD following project template

---

## Development Workflow

### Feature Pipeline (9 Steps)

1. **Idea** → `/new-feature "description"`
2. **PRD** → product-manager creates PRD → **Human Review**
3. **Design** → architect creates design → **Human Review**
4. **Plan** → `/plan` creates implementation plan
5. **Implement** → implementer writes code per plan
6. **Test** → tester writes and runs tests
7. **Review** → code-reviewer does structured review
8. **Validate** → `/validate` final checks
9. **Merge** → `/commit` and PR

### Boundaries

**ALWAYS:**
- Read PRD before implementing
- Follow existing code patterns
- Write tests for acceptance criteria
- Use conventional commits
- Validate before marking done

**ASK FIRST:**
- Adding new dependencies
- Changing database schemas or API contracts
- Modifying CI/CD pipelines
- Changing architectural decisions

**NEVER:**
- Commit secrets, tokens, or passwords
- Push directly to main/master
- Remove tests or security measures
- Skip validation steps
- Make changes outside current task scope

---

## Hooks System

### Architecture

```
PreToolUse(Skill)  → pre-skill-check.sh  → inject health context
PostToolUse(Skill) → log-skill-result.sh  → log execution metadata
                   → post-skill-eval.sh   → evaluate output quality
Stop               → session-report.sh    → session health summary
```

### Self-Improvement Loop

Two-layer approach:
1. **Passive Monitoring** — Hooks automatically log and evaluate every skill execution
2. **Active Improvement** — `/self-improve` runs Karpathy loop: eval → tweak → eval → commit/revert

### Data Flow

```
skill execution → log-skill-result.sh → .claude/hooks/logs/skill-executions-YYYY-MM-DD.jsonl
                → post-skill-eval.sh  → .claude/hooks/logs/eval-results-YYYY-MM-DD.jsonl
                                      → .claude/hooks/metrics/<skill>.jsonl
session end     → session-report.sh   → .claude/hooks/logs/session-report-DATE-PID.md
```

---

## Context Management

- Spawn a fresh sub-agent per phase to prevent context degradation
- Pass minimal necessary context between phases
- Use `docs/state/STATE.md` for persistence across sessions
- Use `/prime` to bootstrap context at session start
