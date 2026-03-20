#!/usr/bin/env bash
# Binary assertion evaluation engine for skill outputs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

# Evaluate a single assertion against output
# Usage: eval_assertion <assertion_type> <assertion_value> <output_text>
# Returns: 0 = pass, 1 = fail
eval_assertion() {
  local type="$1"
  local value="$2"
  local output="$3"

  case "$type" in
    contains)
      echo "$output" | grep -qi "$value"
      ;;
    not_contains)
      ! echo "$output" | grep -qi "$value"
      ;;
    min_words)
      local wc
      wc=$(echo "$output" | wc -w | tr -d ' ')
      [[ "$wc" -ge "$value" ]]
      ;;
    max_words)
      local wc
      wc=$(echo "$output" | wc -w | tr -d ' ')
      [[ "$wc" -le "$value" ]]
      ;;
    has_heading)
      echo "$output" | grep -qP "^#{1,6}\s+.*$value"
      ;;
    has_code_block)
      echo "$output" | grep -q '```'
      ;;
    has_bullet_list)
      echo "$output" | grep -qP '^\s*[-*+]\s+'
      ;;
    min_sections)
      local sections
      sections=$(echo "$output" | grep -cP '^#{2,6}\s+' || echo 0)
      [[ "$sections" -ge "$value" ]]
      ;;
    max_line_length)
      local max_len
      max_len=$(echo "$output" | awk '{ print length }' | sort -rn | head -1)
      [[ "${max_len:-0}" -le "$value" ]]
      ;;
    first_line_contains)
      echo "$output" | head -1 | grep -qi "$value"
      ;;
    last_line_contains)
      echo "$output" | tail -1 | grep -qi "$value"
      ;;
    matches_regex)
      echo "$output" | grep -qP "$value"
      ;;
    has_numbers)
      echo "$output" | grep -qP '\d+'
      ;;
    no_forbidden_chars)
      ! echo "$output" | grep -qP "$value"
      ;;
    needs_ai)
      # Cannot be evaluated automatically, always passes
      return 0
      ;;
    *)
      log_msg "WARN" "Unknown assertion type: $type"
      return 1
      ;;
  esac
}

# Evaluate all assertions from an eval.json file against output
# Usage: eval_all <eval_json_file> <output_text>
# Prints: passed failed total score
eval_all() {
  local eval_file="$1"
  local output="$2"

  local passed=0
  local failed=0
  local total=0

  # Parse assertions from eval.json (simplified — works without jq)
  # Each assertion line: "type": "value"
  local in_assertions=false

  while IFS= read -r line; do
    if echo "$line" | grep -q '"assertions"'; then
      in_assertions=true
      continue
    fi

    if $in_assertions && echo "$line" | grep -q '"type"'; then
      local atype
      atype=$(echo "$line" | grep -oP '"type"\s*:\s*"[^"]*"' | sed 's/.*"type" *: *"//;s/"$//')

      # Read next line for value
      IFS= read -r value_line
      local avalue
      avalue=$(echo "$value_line" | grep -oP '"value"\s*:\s*("[^"]*"|[0-9]+|true|false)' | sed 's/.*"value" *: *//;s/^"//;s/"$//')

      total=$((total + 1))

      if eval_assertion "$atype" "$avalue" "$output" 2>/dev/null; then
        passed=$((passed + 1))
      else
        failed=$((failed + 1))
        log_msg "EVAL" "FAIL: $atype = $avalue"
      fi
    fi

    # End of assertions array
    if $in_assertions && echo "$line" | grep -q '^\s*\]'; then
      in_assertions=false
    fi
  done < "$eval_file"

  local score=0
  if [[ "$total" -gt 0 ]]; then
    score=$((passed * 100 / total))
  fi

  echo "$passed $failed $total $score"
}
