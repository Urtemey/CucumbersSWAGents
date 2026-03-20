#!/usr/bin/env bash
# PostToolUse hook: logs skill execution metadata
# Runs after every Skill tool use

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/utils.sh"

# Read tool input from stdin
INPUT=$(cat)

# Extract skill name
SKILL_NAME=$(echo "$INPUT" | grep -oP '"skill"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"skill" *: *"//;s/"$//' || echo "unknown")

# Skip meta-skills
if is_meta_skill "$SKILL_NAME" 2>/dev/null; then
  exit 0
fi

# Extract args if present
SKILL_ARGS=$(echo "$INPUT" | grep -oP '"args"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"args" *: *"//;s/"$//' || echo "")

# Log execution
LOG_DIR="$(get_logs_dir)"
LOG_FILE="$LOG_DIR/skill-executions-$(get_today).jsonl"

TIMESTAMP="$(get_timestamp)"
LOG_ENTRY="{\"timestamp\":\"$TIMESTAMP\",\"skill\":\"$SKILL_NAME\",\"args\":\"$SKILL_ARGS\"}"

append_jsonl "$LOG_FILE" "$LOG_ENTRY"
