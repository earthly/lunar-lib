#!/bin/bash
# The oncall (code hook) and oncall-cron (daily) sub-collectors.
set -e

# shellcheck source=collectors/pagerduty/helpers.sh disable=SC1091
source "$(dirname "$0")/helpers.sh"

require_api_key

# Component meta, then the explicit input, then backstage_discovery.
resolve_meta_and_input

if [ -z "$SERVICE_ID" ]; then
  case "$DISCOVERY" in
    false) ;;
    true)
      resolve_from_checkout
      ;;
    live)
      case "${LUNAR_COLLECTOR_NAME:-}" in
        *oncall-cron)
          # The daily refresh reads the backstage collector's lookup off the
          # default branch's current JSON. It isn't dispatched off a record, so
          # a short retry is enough, and the next run tries again.
          read_component_json 30 false
          if [ "$READ_STATE" != "ok" ]; then
            echo "backstage_discovery: live, but the Component JSON has no Backstage lookup (.catalog.native.backstage.refs.entity) yet. Is the backstage collector running with backstage_url set? Skipping this refresh." >&2
            exit 0
          fi
          resolve_from_backstage_json "$COMPONENT_JSON"
          ;;
        *)
          echo "backstage_discovery: live. The backstage sub-collector resolves this component's service once the backstage collector's lookup lands." >&2
          exit 0
          ;;
      esac
      ;;
    *)
      echo "Invalid backstage_discovery '$DISCOVERY' (expected false, true or live). Writing nothing." >&2
      exit 0
      ;;
  esac
fi

[ -n "$SERVICE_ID" ] || finish_unresolved
collect_pagerduty
