#!/usr/bin/env bash
# Stop hook: generates session health summary report
# Runs when Claude Code session ends

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/utils.sh"
source "$SCRIPT_DIR/lib/metrics.sh"

LOG_DIR="$(get_logs_dir)"
TODAY="$(get_today)"
SESSION_ID="$$"

# Check if there were any skill executions today
EXEC_LOG="$LOG_DIR/skill-executions-$TODAY.jsonl"
if [[ ! -f "$EXEC_LOG" ]]; then
  exit 0
fi

# Count executions
EXEC_COUNT=$(wc -l < "$EXEC_LOG" | tr -d ' ')
if [[ "$EXEC_COUNT" -eq 0 ]]; then
  exit 0
fi

# Generate report
REPORT_FILE="$LOG_DIR/session-report-$TODAY-$SESSION_ID.md"

{
  echo "# Session Health Report"
  echo ""
  echo "**Date**: $TODAY"
  echo "**Session**: $SESSION_ID"
  echo "**Total skill executions**: $EXEC_COUNT"
  echo ""
  echo "## Skill Scores"
  echo ""
  echo "| Skill | Score | Best | Trend |"
  echo "|-------|-------|------|-------|"

  # Get summary for all skills with metrics
  SUMMARY=$(get_all_skills_summary)
  if [[ -n "$SUMMARY" ]]; then
    while IFS=' ' read -r skill latest best trend; do
      TREND_ICON="→"
      [[ "$trend" == "up" ]] && TREND_ICON="↑"
      [[ "$trend" == "down" ]] && TREND_ICON="↓"
      echo "| $skill | ${latest}% | ${best}% | $TREND_ICON |"
    done <<< "$SUMMARY"
  fi

  echo ""
  echo "## Recommendations"
  echo ""

  # Find skills below threshold
  THRESHOLD="${SKILL_EVAL_THRESHOLD:-80}"
  NEEDS_IMPROVE=""

  if [[ -n "$SUMMARY" ]]; then
    while IFS=' ' read -r skill latest best trend; do
      if [[ "$latest" -lt "$THRESHOLD" ]] 2>/dev/null; then
        NEEDS_IMPROVE="$NEEDS_IMPROVE\n- \`/self-improve $skill\` (score: ${latest}%)"
      fi
    done <<< "$SUMMARY"
  fi

  if [[ -n "$NEEDS_IMPROVE" ]]; then
    echo "Skills below threshold ($THRESHOLD%):"
    echo -e "$NEEDS_IMPROVE"
  else
    echo "All evaluated skills are above threshold. Great job!"
  fi

} > "$REPORT_FILE"

echo "[Session Report] Saved to $REPORT_FILE"
