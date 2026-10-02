#!/bin/bash
# The backstage sub-collector: with backstage_discovery: live, finds the
# component's PagerDuty service in the Backstage lookup the backstage collector
# wrote to Component JSON, then queries PagerDuty. Dispatched by an after-json
# hook on .catalog.native.backstage.refs.entity.
set -e

# shellcheck source=collectors/pagerduty/helpers.sh disable=SC1091
source "$(dirname "$0")/helpers.sh"

if [ "$DISCOVERY" != "live" ]; then
  echo "backstage_discovery is '$DISCOVERY', not 'live': the oncall sub-collector handles this component." >&2
  exit 0
fi

require_api_key

resolve_meta_and_input
if [ -n "$SERVICE_ID" ]; then
  echo "The service ID comes from $DISCOVERED_VIA, which the oncall sub-collector collects." >&2
  exit 0
fi

WAIT_SECONDS="${LUNAR_VAR_BACKSTAGE_WAIT_SECONDS:-1800}"
if ! [[ "$WAIT_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "Invalid backstage_wait_seconds '$WAIT_SECONDS'; using 1800." >&2
  WAIT_SECONDS=1800
fi

read_component_json "$WAIT_SECONDS" true
case "$READ_STATE" in
  ok) ;;
  read_failed)
    echo "Could not read Component JSON for ${LUNAR_COMPONENT_ID:-?} after ${WAITED}s across ${ATTEMPT} attempt(s); see the get-json error above." >&2
    echo "Failing the run: the after-json wave is fire-once per commit, so this commit's PagerDuty data is lost unless a new commit runs it again." >&2
    exit 1
    ;;
  no_lookup)
    # This run was dispatched because that path is in the live blob, so its
    # absence here means the read is behind, not that the lookup didn't happen.
    echo "The backstage collector's lookup (.catalog.native.backstage.refs.entity) still isn't readable after ${WAITED}s across ${ATTEMPT} attempt(s). This commit's row has most likely not materialized yet." >&2
    echo "Failing the run: the after-json wave is fire-once per commit. Raise backstage_wait_seconds if this keeps happening." >&2
    exit 1
    ;;
esac

resolve_from_backstage_json "$COMPONENT_JSON"
[ -n "$SERVICE_ID" ] || finish_unresolved
collect_pagerduty
