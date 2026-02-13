#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Find the DR plan document
if ! find_file "$LUNAR_VAR_PLAN_PATHS"; then
  lunar collect -j ".oncall.disaster_recovery.plan" '{"exists": false}'
  exit 0
fi

FM=$(extract_frontmatter "$FOUND_FILE")
BODY=$(extract_body "$FOUND_FILE")
SECTIONS=$(extract_sections "$BODY")

RTO_MINUTES=$(parse_field "$FM" "rto_minutes")
RPO_MINUTES=$(parse_field "$FM" "rpo_minutes")
LAST_REVIEWED=$(parse_field "$FM" "last_reviewed")
APPROVER=$(parse_field "$FM" "approver")
DAYS_SINCE_REVIEW=$(days_since "$LAST_REVIEWED")

jq -n \
  --arg path "$FOUND_PATH" \
  --arg rto "$RTO_MINUTES" \
  --arg rpo "$RPO_MINUTES" \
  --arg lr "$LAST_REVIEWED" \
  --arg dsr "$DAYS_SINCE_REVIEW" \
  --arg approver "$APPROVER" \
  --argjson sections "${SECTIONS:-[]}" \
  '{exists: true, path: $path}
   + {rto_defined: ($rto != "")}
   + if $rto != "" then {rto_minutes: ($rto | tonumber)} else {} end
   + {rpo_defined: ($rpo != "")}
   + if $rpo != "" then {rpo_minutes: ($rpo | tonumber)} else {} end
   + if $lr != "" then {last_reviewed: $lr} else {} end
   + if $dsr != "" then {days_since_review: ($dsr | tonumber)} else {} end
   + if $approver != "" then {approver: $approver} else {} end
   + {sections: $sections}' \
  | lunar collect -j ".oncall.disaster_recovery.plan" -
