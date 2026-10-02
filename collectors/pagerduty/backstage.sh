#!/bin/bash
# The backstage sub-collector: finds the component's PagerDuty service in what
# the backstage collector read from the live catalog (the Component, else its
# System, else that System's Domain), for components the oncall sub-collector
# can't map from meta, service_id or, with backstage_discovery: "true", the
# catalog file. Dispatched by an after-json hook on
# .catalog.native.backstage.refs.entity.
set -e

# shellcheck source=collectors/pagerduty/helpers.sh disable=SC1091
source "$(dirname "$0")/helpers.sh"

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

if [ "$DISCOVERY" = "true" ] && [ -n "$(file_id_from_backstage_json "$COMPONENT_JSON")" ]; then
  echo "The service ID is in the catalog file, which the oncall sub-collector reads with backstage_discovery: \"true\"." >&2
  exit 0
fi

# The oncall sub-collector records meta, the input and the file as searched.
# shellcheck disable=SC2034  # read by finish_unresolved
SEARCHED=()
resolve_from_backstage_json "$COMPONENT_JSON"
[ -n "$SERVICE_ID" ] || finish_unresolved
collect_pagerduty
