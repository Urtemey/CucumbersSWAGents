#!/usr/bin/env bash
# PostToolUse hook: evaluates skill output quality using eval.json assertions
# Runs after every Skill tool use

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/utils.sh"
source "$SCRIPT_DIR/lib/metrics.sh"
source "$SCRIPT_DIR/lib/eval-engine.sh"

# Read tool output from stdin
INPUT=$(cat)

# Extract skill name
SKILL_NAME=$(echo "$INPUT" | grep -oP '"skill"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"skill" *: *"//;s/"$//' || echo "unknown")

# Skip meta-skills
if is_meta_skill "$SKILL_NAME" 2>/dev/null; then
  exit 0
fi

# Check if eval.json exists for this skill
PROJECT_DIR="$(get_project_dir)"
EVAL_FILE="$PROJECT_DIR/.claude/skills/$SKILL_NAME/eval.json"

if [[ ! -f "$EVAL_FILE" ]]; then
  # No eval file — skip evaluation
  exit 0
fi

# Extract the tool output/response for evaluation
TOOL_OUTPUT=$(echo "$INPUT" | grep -oP '"output"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"output" *: *"//;s/"$//' || echo "")

if [[ -z "$TOOL_OUTPUT" ]]; then
  exit 0
fi

# Run evaluation
RESULT=$(eval_all "$EVAL_FILE" "$TOOL_OUTPUT")
read -r PASSED FAILED TOTAL SCORE <<< "$RESULT"

# Record score
record_score "$SKILL_NAME" "$SCORE" "passed=$PASSED failed=$FAILED total=$TOTAL"

# Log eval result
LOG_DIR="$(get_logs_dir)"
LOG_FILE="$LOG_DIR/eval-results-$(get_today).jsonl"
TIMESTAMP="$(get_timestamp)"
LOG_ENTRY="{\"timestamp\":\"$TIMESTAMP\",\"skill\":\"$SKILL_NAME\",\"score\":$SCORE,\"passed\":$PASSED,\"failed\":$FAILED,\"total\":$TOTAL}"
append_jsonl "$LOG_FILE" "$LOG_ENTRY"

# Output result
echo "[Skill Eval] $SKILL_NAME: score=$SCORE% ($PASSED/$TOTAL passed)"

# Suggest self-improve if below threshold
THRESHOLD="${SKILL_EVAL_THRESHOLD:-80}"
if [[ "$SCORE" -lt "$THRESHOLD" ]]; then
  echo "[Skill Eval] ⚠ Below threshold. Run: /self-improve $SKILL_NAME"
fi
