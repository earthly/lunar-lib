set -e

if [ -z "$LUNAR_COMPONENT_PR" ]; then
  # Since Semgrep doesn't post Github Checks to the main branch,
  # we use this DB query to check if the Snyk Github app has been run on PRs recently.
  # This allows us to show proof on the main branch that the component is running Snyk scans on PRs.
  # (Alternatlively, we could also use Semgrep API but Enterprise plans are required)
  QUERY="
    SELECT EXISTS (
        SELECT 1
        FROM components_latest pr
        WHERE pr.component_id = '$LUNAR_COMPONENT_ID'
          AND pr.pr IS NOT NULL
          AND (pr.component_json->'sca'->>'run')::boolean IS TRUE
          AND jsonb_path_exists(pr.component_json, '$.sca.semgrep.github_app_results')
    ) AS snyk_present;
  "

  RESULT="$(PGPASSWORD="$LUNAR_SECRET_PG_PASSWORD" psql -t -A -h postgres -U "testuser" -d hub -c "$QUERY")"
  if [ "$RESULT" = "t" ]; then
    lunar collect -j ".sca.semgrep.github_app_run_recently" true "sca.run" true
  fi
  exit 0
fi

REPO="${LUNAR_COMPONENT_ID#github.com/}"
QUICK_ATTEMPTS=3
LONG_ATTEMPTS=60
SLEEP_SECONDS=2

# API call to Github to check for Semgrep in check-runs
CURL_CMD="curl -fsS \
  -H 'Accept: application/vnd.github+json' \
  -H 'Authorization: token $LUNAR_SECRET_GH_TOKEN' \
  'https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/check-runs' | \
  jq -c '.check_runs | \
    map(select(.app.slug | test(\"semgrep\";\"i\"))) | \
    first | \
    select(. != null) | \
    {id, name, status, conclusion, details_url, html_url, started_at, completed_at, app: {slug: .app.slug}}' 2>/dev/null || echo 'null'"

J=""
FOUND_CHECK=false

# First check for a short while if Semgrep is showing up in the list or not.
for i in $(seq 1 $QUICK_ATTEMPTS); do
  J="$(eval "$CURL_CMD" || echo "null")"
  if [ -n "$J" ] && [ "$J" != "null" ]; then
    FOUND_CHECK=true
    break
  fi
  sleep "$SLEEP_SECONDS"
done

# Exit quickly if no check found
[ "$FOUND_CHECK" = "false" ] && exit 0

# If Semgrep is in the list, it can take a while for it to finish scanning.
# This will wait until the scan completes and collect the results.
for i in $(seq $((QUICK_ATTEMPTS + 1)) $LONG_ATTEMPTS); do
  STATE=$(echo "$J" | jq -r '.state // .status // empty' 2>/dev/null || echo "")
  if [ "$STATE" = "pending" ] || [ "$STATE" = "queued" ] || [ "$STATE" = "in_progress" ]; then
    sleep "$SLEEP_SECONDS"
    J="$(eval "$CURL_CMD" || echo "null")"
    continue
  fi
  break
done

[ -n "$J" ] && [ "$J" != "null" ] && lunar collect -j ".sca.semgrep.github_app_results" "$J" ".sca.run" true
