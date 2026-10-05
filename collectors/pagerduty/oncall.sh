#!/bin/bash
# The oncall (code hook) and oncall-cron (daily) sub-collectors.
set -e

# shellcheck source=collectors/pagerduty/helpers.sh disable=SC1091
source "$(dirname "$0")/helpers.sh"

require_api_key

# Component meta, then the explicit input, then (backstage_discovery: "true")
# the checked-out catalog-info.yaml.
resolve_meta_and_input
if [ -z "$SERVICE_ID" ] && [ "$DISCOVERY" = "true" ]; then
  resolve_from_checkout
fi

# The daily refresh also reads what the backstage collector found in the live
# catalog, from the default branch's Component JSON, so a service inherited
# from a System or Domain stays fresh. On push that's the backstage
# sub-collector's job, since the lookup may not have landed yet.
if [ -z "$SERVICE_ID" ]; then
  case "${LUNAR_COLLECTOR_NAME:-}" in
    *oncall-cron)
      read_component_json 0 false
      case "$READ_STATE" in
        ok) resolve_from_backstage_json "$COMPONENT_JSON" ;;
        # No live lookup to read: the backstage collector isn't set up with
        # backstage_url, or this repo has no catalog file.
        no_lookup) ;;
        *)
          echo "Could not read the default branch's Component JSON; skipping this refresh." >&2
          exit 0
          ;;
      esac
      ;;
  esac
fi

if [ -z "$SERVICE_ID" ]; then
  hint="The from-backstage-collector sub-collector, if included, looks in the live catalog next."
  if [ "$DISCOVERY" != "true" ]; then
    hint="Map it with the 'pagerduty/service-id' meta, the service_id input or, with backstage_discovery: \"true\", catalog-info.yaml. $hint"
  fi
  finish_unresolved "$hint"
fi
collect_pagerduty
