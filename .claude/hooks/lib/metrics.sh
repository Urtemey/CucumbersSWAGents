#!/usr/bin/env bash
# Metrics tracking for skill evaluations

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

# Record a score for a skill
# Usage: record_score <skill-name> <score> [details]
record_score() {
  local skill="$1"
  local score="$2"
  local details="${3:-}"
  local metrics_dir="$(get_metrics_dir)"
  local file="$metrics_dir/${skill}.jsonl"
  local timestamp="$(get_timestamp)"

  local json="{\"timestamp\":\"$timestamp\",\"score\":$score,\"details\":\"$details\"}"
  append_jsonl "$file" "$json"
}

# Get latest score for a skill
# Usage: get_latest_score <skill-name>
get_latest_score() {
  local skill="$1"
  local file="$(get_metrics_dir)/${skill}.jsonl"

  if [[ -f "$file" ]]; then
    tail -1 "$file" | grep -oP '"score"\s*:\s*[0-9]+' | grep -oP '[0-9]+$'
  else
    echo "-1"
  fi
}

# Get best score for a skill
# Usage: get_best_score <skill-name>
get_best_score() {
  local skill="$1"
  local file="$(get_metrics_dir)/${skill}.jsonl"

  if [[ -f "$file" ]]; then
    grep -oP '"score"\s*:\s*[0-9]+' "$file" | grep -oP '[0-9]+$' | sort -rn | head -1
  else
    echo "-1"
  fi
}

# Get score trend for a skill (up/down/stable)
# Compares last 2 scores
get_trend() {
  local skill="$1"
  local file="$(get_metrics_dir)/${skill}.jsonl"

  if [[ ! -f "$file" ]]; then
    echo "none"
    return
  fi

  local count
  count=$(wc -l < "$file")

  if [[ "$count" -lt 2 ]]; then
    echo "none"
    return
  fi

  local last
  last=$(tail -1 "$file" | grep -oP '"score"\s*:\s*[0-9]+' | grep -oP '[0-9]+$')
  local prev
  prev=$(tail -2 "$file" | head -1 | grep -oP '"score"\s*:\s*[0-9]+' | grep -oP '[0-9]+$')

  if [[ "$last" -gt "$prev" ]]; then
    echo "up"
  elif [[ "$last" -lt "$prev" ]]; then
    echo "down"
  else
    echo "stable"
  fi
}

# Get summary for all skills
# Output: skill_name latest_score best_score trend
get_all_skills_summary() {
  local metrics_dir="$(get_metrics_dir)"

  for file in "$metrics_dir"/*.jsonl; do
    [[ -f "$file" ]] || continue
    local skill
    skill=$(basename "$file" .jsonl)
    local latest
    latest=$(get_latest_score "$skill")
    local best
    best=$(get_best_score "$skill")
    local trend
    trend=$(get_trend "$skill")
    echo "$skill $latest $best $trend"
  done
}

# Get improvement delta (latest - first score)
get_improvement_delta() {
  local skill="$1"
  local file="$(get_metrics_dir)/${skill}.jsonl"

  if [[ ! -f "$file" ]]; then
    echo "0"
    return
  fi

  local first
  first=$(head -1 "$file" | grep -oP '"score"\s*:\s*[0-9]+' | grep -oP '[0-9]+$')
  local last
  last=$(tail -1 "$file" | grep -oP '"score"\s*:\s*[0-9]+' | grep -oP '[0-9]+$')

  echo $((last - first))
}
