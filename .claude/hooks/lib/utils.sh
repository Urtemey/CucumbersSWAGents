#!/usr/bin/env bash
# Shared utility functions for hooks

set -euo pipefail

# Resolve project root directory
get_project_dir() {
  echo "${CLAUDE_PROJECT_DIR:-.}"
}

# Get hooks directory
get_hooks_dir() {
  echo "$(get_project_dir)/.claude/hooks"
}

# Get metrics directory (create if needed)
get_metrics_dir() {
  local dir="$(get_hooks_dir)/metrics"
  mkdir -p "$dir"
  echo "$dir"
}

# Get logs directory (create if needed)
get_logs_dir() {
  local dir="$(get_hooks_dir)/logs"
  mkdir -p "$dir"
  echo "$dir"
}

# Get today's date in YYYY-MM-DD format
get_today() {
  date +%Y-%m-%d
}

# Get current timestamp in ISO format
get_timestamp() {
  date +%Y-%m-%dT%H:%M:%S
}

# Extract skill name from tool input JSON
# Reads from stdin (hook receives JSON via stdin)
extract_skill_name() {
  local input="$1"
  echo "$input" | grep -oP '"skill_name"\s*:\s*"[^"]*"' | head -1 | grep -oP '"[^"]*"$' | tr -d '"' || echo "unknown"
}

# Check if a skill is a meta-skill (should not be self-evaluated)
is_meta_skill() {
  local skill="$1"
  case "$skill" in
    self-improve|generate-eval|overnight|skill-health|system-review)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Log a message with timestamp
log_msg() {
  local level="$1"
  local msg="$2"
  echo "[$(get_timestamp)] [$level] $msg" >&2
}

# Safe JSON value extraction (no jq dependency)
json_value() {
  local json="$1"
  local key="$2"
  echo "$json" | grep -oP "\"$key\"\s*:\s*\"[^\"]*\"" | head -1 | sed 's/.*: *"//;s/"$//' || echo ""
}

# Safe JSON number extraction
json_number() {
  local json="$1"
  local key="$2"
  echo "$json" | grep -oP "\"$key\"\s*:\s*[0-9]+" | head -1 | grep -oP '[0-9]+$' || echo "0"
}

# Append JSON line to a JSONL file
append_jsonl() {
  local file="$1"
  local json="$2"
  echo "$json" >> "$file"
}
