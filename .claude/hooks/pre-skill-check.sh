#!/usr/bin/env bash
# PreToolUse hook: injects skill health context before skill execution
# Runs before every Skill tool use

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/utils.sh"
source "$SCRIPT_DIR/lib/metrics.sh"

# Read tool input from stdin
INPUT=$(cat)

# Extract skill name from the tool input
SKILL_NAME=$(echo "$INPUT" | grep -oP '"skill"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"skill" *: *"//;s/"$//' || echo "unknown")

# Skip meta-skills to avoid infinite loops
if is_meta_skill "$SKILL_NAME"; then
  exit 0
fi

# Get health metrics for this skill
LATEST=$(get_latest_score "$SKILL_NAME")
BEST=$(get_best_score "$SKILL_NAME")
TREND=$(get_trend "$SKILL_NAME")

# Only output context if we have metrics
if [[ "$LATEST" != "-1" ]]; then
  TREND_ARROW="→"
  [[ "$TREND" == "up" ]] && TREND_ARROW="↑"
  [[ "$TREND" == "down" ]] && TREND_ARROW="↓"

  echo "[Skill Health] $SKILL_NAME: score=$LATEST% (best=$BEST%) trend=$TREND_ARROW"

  # Warn if below threshold
  THRESHOLD="${SKILL_EVAL_THRESHOLD:-80}"
  if [[ "$LATEST" -lt "$THRESHOLD" ]]; then
    echo "[Skill Health] ⚠ Below threshold ($THRESHOLD%). Consider running /self-improve $SKILL_NAME"
  fi
fi
