#!/bin/bash
# ticket-coverage: what share of this component's recent pull requests referenced an
# issue-tracker ticket.
#
# Runs on the default branch and reads Lunar's own history through the SQL API, so it
# needs no issue-tracker or Git-platform credentials and behaves identically on any Git
# platform. Writes .vcs.ticket_coverage, which the ticket-coverage policy scores.
#
# Default-branch placement is the point: every Lunar rollup reads default-branch state
# only, so per-PR ticket results never reach an initiative score.
set -e

# Skip in pull-request context. A per-PR value would be both wrong (the window is a
# property of the component, not of one change) and useless (it would never roll up).
if [ -n "${LUNAR_COMPONENT_PR:-}" ]; then
    echo "In pull-request context; ticket-coverage is a default-branch metric. Skipping." >&2
    exit 0
fi

if [ -z "${LUNAR_COMPONENT_ID:-}" ]; then
    echo "LUNAR_COMPONENT_ID is not set; skipping." >&2
    exit 0
fi

# Reject non-numeric and absurdly long values, then normalise explicitly in base 10 so
# a padded "030" is thirty days rather than bash's octal twenty-four.
WINDOW_INPUT="${LUNAR_VAR_WINDOW_DAYS:-30}"
case "$WINDOW_INPUT" in
    ''|*[!0-9]*|??????*) WINDOW=0 ;;
    *) WINDOW=$((10#$WINDOW_INPUT)) ;;
esac
if [ "$WINDOW" -le 0 ]; then
    echo "window_days must be a positive integer, got '${WINDOW_INPUT}'; using 30." >&2
    WINDOW=30
fi

CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true
if [ -z "$CONN_STRING" ]; then
    echo "SQL API unavailable; skipping." >&2
    exit 0
fi

# psql ships in earthly/lunar-lib:base-main. Reaching here without it means the runtime
# image was overridden with one that cannot run this collector, so say so rather than
# skipping — a silent skip is indistinguishable from "this component has no pull
# requests yet", which is a legitimate result.
if ! command -v psql >/dev/null 2>&1; then
    echo "psql not found; ticket-coverage needs a runtime image with postgresql-client." >&2
    exit 1
fi

# Double any single quote so the id cannot terminate the literal below. Parameter
# expansion rather than echo|sed: echo mangles backslashes in some shells, and a
# component id is attacker-influenced (it is derived from a repository path).
SAFE_COMPONENT_ID="${LUNAR_COMPONENT_ID//\'/\'\'}"

# One row per pull request, newest first, so a PR counts once however many commits it
# carried and its ticket reflects the latest state of the PR.
#
# public.components, not public.materialized_components. `components` is the supported SQL
# API surface, and it is a serving switch on HUB_MAT_SERVING_ENABLED: with the flag on the
# view reads mat.components, with it off it reads components_base UNION
# materialized_components and prefers components_base. So materialized_components is either
# not in the serving path at all, or only its stale arm -- reading it directly undercounts
# recent pull requests, which for a trailing window is exactly the rows that matter. Both
# branches of the switch are required to expose an identical column list, which is what
# makes `components` safe to depend on across the flip.
#
# Not components_latest: this needs the trailing-window *history* of pull requests, and
# components_latest is filtered to the latest commits per component.
#
# `timestamp` is `timestamp without time zone` holding UTC, so the window is anchored on
# `now() AT TIME ZONE 'UTC'`. A bare now() is timestamptz and gets compared through the
# session time zone, silently shifting the window by that offset.
QUERY="
  WITH prs AS (
    SELECT DISTINCT ON (pr)
           pr,
           component_json->'vcs'->'pr'->'ticket'->>'id' AS ticket_id
    FROM public.components
    WHERE component_id = '${SAFE_COMPONENT_ID}'
      AND pr IS NOT NULL
      AND timestamp > (now() AT TIME ZONE 'UTC') - interval '${WINDOW} days'
    ORDER BY pr, timestamp DESC
  )
  SELECT count(*), count(ticket_id) FROM prs;
"

ROW=$(psql "$CONN_STRING" -tA -F'|' -c "$QUERY" 2>&1) || true

PRS_TOTAL="${ROW%%|*}"
PRS_WITH_TICKET="${ROW##*|}"

# The connection string resolved, so a result that is not two integers is a real
# failure (bad query, unreachable database, revoked grant) rather than an absent
# feature. Report it instead of writing a misleading zero.
case "$PRS_TOTAL" in
    ''|*[!0-9]*)
        echo "Failed to query pull-request history: ${ROW}" >&2
        exit 1
        ;;
esac
case "$PRS_WITH_TICKET" in
    ''|*[!0-9]*) PRS_WITH_TICKET=0 ;;
esac

# An empty window is recorded rather than skipped, with a null percentage. The policy
# skips on it either way, but writing it keeps "collected, no pull requests in the
# window" distinguishable from "this collector never ran".
if [ "$PRS_TOTAL" -eq 0 ]; then
    echo "No pull requests recorded for ${LUNAR_COMPONENT_ID} in the last ${WINDOW}d." >&2
    jq -n --argjson window "$WINDOW" \
        '{window_days: $window, prs_total: 0, prs_with_ticket: 0, percentage: null}' \
        | lunar collect -j ".vcs.ticket_coverage" -
    exit 0
fi

PERCENTAGE=$(awk -v n="$PRS_WITH_TICKET" -v d="$PRS_TOTAL" 'BEGIN { printf "%.1f", (n / d) * 100 }')

jq -n \
    --argjson window "$WINDOW" \
    --argjson total "$PRS_TOTAL" \
    --argjson with_ticket "$PRS_WITH_TICKET" \
    --argjson percentage "$PERCENTAGE" \
    '{
        window_days: $window,
        prs_total: $total,
        prs_with_ticket: $with_ticket,
        percentage: $percentage
    }' \
    | lunar collect -j ".vcs.ticket_coverage" -

echo "ticket-coverage for ${LUNAR_COMPONENT_ID}: ${PRS_WITH_TICKET}/${PRS_TOTAL} pull requests (${PERCENTAGE}%) over ${WINDOW}d" >&2
