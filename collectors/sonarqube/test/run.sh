#!/bin/bash
# Offline end-to-end test for api.sh: the real script and helpers.sh, curl, jq,
# git and lunar CLI against test/sonarqube.py, a SonarQube Web API stand-in
# that, like the real server, ignores pullRequest on
# api/project_analyses/search. sleep is stubbed, so polls are instant and a 30s
# timeout at a 10s interval is exactly 3 polls.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../api.sh"
TMP="$(mktemp -d)"

python3 "$HERE/sonarqube.py" "$TMP/requests.log" "$TMP/port" > "$TMP/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; rm -rf "$TMP"' EXIT
for _ in $(seq 1 50); do [ -s "$TMP/port" ] && break; sleep 0.1; done
PORT="$(cat "$TMP/port")"

mkdir -p "$TMP/bin" "$TMP/nogit"
printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/sleep"
chmod +x "$TMP/bin/sleep"

# The checkout the code hook runs in: one commit, committed at 10:00:00Z.
REPO="$TMP/repo"
git init -q "$REPO"
GIT_COMMITTER_DATE="2026-11-10 10:00:00 +0000" GIT_AUTHOR_DATE="2026-11-10 10:00:00 +0000" \
  git -C "$REPO" -c user.name=test -c user.email=test@example.com commit -q --allow-empty -m head
HEAD_SHA="$(git -C "$REPO" rev-parse HEAD)"
OLD_SHA=1111111111111111111111111111111111111111  # the PR's previous head
MAIN_SHA=2222222222222222222222222222222222222222 # main's newest analysis

PR_ENV=(LUNAR_COMPONENT_PR=42 LUNAR_COMPONENT_HEAD_BRANCH=feature/x LUNAR_COMPONENT_BASE_BRANCH=main)

# PR list entries. SonarCloud reports the analyzed commit; SonarQube Server doesn't.
cloud_pr() { # cloud_pr <key> <sha> <analysisDate>
  jq -nc --arg k "$1" --arg sha "$2" --arg d "$3" \
    '{key: $k, title: "Add widgets", branch: "feature/x", base: "main", target: "main",
      status: {qualityGateStatus: "ERROR"}, analysisDate: $d, commit: {sha: $sha}}'
}
server_pr() { # server_pr <key> <analysisDate>
  jq -nc --arg k "$1" --arg d "$2" \
    '{key: $k, title: "Add widgets", branch: "feature/x", base: "main", target: "main",
      status: {qualityGateStatus: "ERROR"}, analysisDate: $d, pullRequestId: "AZ-pr"}'
}

FAILED=0
CASE=""

# run_case <name> <scenario> [VAR=value ...]: loads the scenario into the
# stand-in and runs api.sh in a clean env from the checkout (or $CWD), as the
# code hook would. Leaves the merged Component JSON in $CJ, requests in $REQ.
run_case() {
  CASE="$1"; printf '%s' "$2" > "$TMP/$CASE.scenario.json"; shift 2
  curl -fsS "http://127.0.0.1:$PORT/__load?file=$TMP/$CASE.scenario.json" > /dev/null
  OUT="$TMP/$CASE.out"; ERR="$TMP/$CASE.err"; CJ="$TMP/$CASE.json"; REQ="$TMP/$CASE.requests"
  (cd "${CWD:-$REPO}" && env -i PATH="$TMP/bin:$PATH" HOME="$TMP" \
    LUNAR_COLLECT_STDOUT=1 \
    LUNAR_COMPONENT_ID=github.com/acme/widgets \
    LUNAR_COMPONENT_GIT_SHA="$HEAD_SHA" \
    LUNAR_SECRET_SONARQUBE_TOKEN=test-token \
    LUNAR_VAR_SONARQUBE_BASE_URL="http://127.0.0.1:$PORT" \
    LUNAR_VAR_PROJECT_KEY=acme_widgets \
    LUNAR_VAR_API_POLL_TIMEOUT_SECONDS=30 \
    LUNAR_VAR_API_POLL_INTERVAL_SECONDS=10 \
    "$@" bash "$SCRIPT" > "$OUT" 2> "$ERR")
  CODE=$?
  cp "$TMP/requests.log" "$REQ"
  jq -s 'reduce .[] as $i ({}; . * $i)' "$OUT" > "$CJ"
}

pass() { echo "ok   [$CASE] $1"; }
fail() {
  echo "FAIL [$CASE] $1"
  sed 's/^/       stderr: /' "$ERR"
  FAILED=$((FAILED + 1))
}
expect() { # expect <description> <command...>
  local desc="$1"; shift
  if "$@" > /dev/null 2>&1; then pass "$desc"; else fail "$desc"; fi
}
cj() { jq -e "$1" "$CJ"; }
count() { [ "$(grep -cE -- "$1" "$REQ")" -eq "$2" ]; } # count <ERE> <n>
logged() { grep -qF -- "$1" "$ERR"; }

expect_pr_complete() {
  expect "exits 0" test "$CODE" -eq 0
  expect "writes analysis_status complete" cj '.code_quality.source | .integration == "api" and .analysis_status == "complete"'
  expect "writes the PR's measures" cj '.code_quality | .coverage_percentage == 91.5 and .passing == false
    and .issues == {total: 7, critical: 1, high: 2, medium: 4, low: 0}
    and .native.sonarqube.quality_gate == {status: "ERROR", conditions_failed: 1}'
  expect "reads measures, gate and issues with pullRequest=42" \
    count '^/api/(measures/component|qualitygates/project_status|issues/search)\?.*&pullRequest=42$' 3
  expect "never asks project_analyses/search" count project_analyses/search 0
}
expect_branch_complete() {
  expect "exits 0" test "$CODE" -eq 0
  expect "writes analysis_status complete" cj '.code_quality.source | .integration == "api" and .analysis_status == "complete"'
  expect "writes the branch's measures" cj '.code_quality | .coverage_percentage == 78.3 and .passing == true
    and .issues == {total: 46, critical: 0, high: 1, medium: 3, low: 42}
    and .native.sonarqube.quality_gate == {status: "OK", conditions_failed: 0}'
  expect "never sends pullRequest" count pullRequest= 0
}
expect_pending() {
  expect "exits 0" test "$CODE" -eq 0
  expect "writes analysis_status pending and nothing else" \
    cj '(.code_quality | keys) == ["source"] and .code_quality.source.analysis_status == "pending"'
  expect "reads no measures" count /api/measures/component 0
}

# --- Default branch: unchanged, matched on project_analyses/search's revision.

run_case main-complete "$(jq -nc --arg h "$HEAD_SHA" '{analyses: {main: [$h]}}')"
expect_branch_complete
expect "matches on the first poll" count '^/api/project_analyses/search\?project=acme_widgets&ps=1$' 1

run_case main-pending-then-complete \
  "$(jq -nc --arg o "$OLD_SHA" --arg h "$HEAD_SHA" '{analyses: {main: [$o, $o, $h]}}')"
expect_branch_complete
expect "polls until the analysis lands (3 polls)" count project_analyses/search 3

run_case main-timeout "$(jq -nc --arg o "$OLD_SHA" '{analyses: {main: [$o]}}')"
expect_pending
expect "gives up after 3 polls" count project_analyses/search 3
expect "logs the timeout" logged "analysis for $HEAD_SHA did not appear within 30s"

# --- PR commits. main's newest analysis is MAIN_SHA throughout, which is what
# project_analyses/search?pullRequest=42 answers, so polling it never matched.

run_case pr-only-sonarcloud "$(jq -nc --arg m "$MAIN_SHA" --argjson e "$(cloud_pr 42 "$HEAD_SHA" 2026-11-10T10:04:00+0000)" \
  '{analyses: {main: [$m]}, pull_requests: [[$e]]}')" "${PR_ENV[@]}"
expect_pr_complete
expect "matches on the first poll" count '^/api/project_pull_requests/list\?project=acme_widgets$' 1

# Server has no commit on the entry: 12:03+0200 is 10:03Z, after the 10:00Z commit.
run_case pr-only-server "$(jq -nc --arg m "$MAIN_SHA" --argjson e "$(server_pr 42 2026-11-10T12:03:00+0200)" \
  '{analyses: {main: [$m]}, pull_requests: [[$e]]}')" "${PR_ENV[@]}"
expect_pr_complete

run_case pr-also-published-as-branch "$(jq -nc --arg m "$MAIN_SHA" --arg h "$HEAD_SHA" \
  --argjson e "$(cloud_pr 42 "$HEAD_SHA" 2026-11-10T10:04:00+0000)" \
  '{analyses: {main: [$m], "feature/x": [$h]}, pull_requests: [[$e]]}')" "${PR_ENV[@]}"
expect_pr_complete
expect "never reads the head branch" count branch=feature/x 0

# The head branch's own analysis already has the commit; the PR's doesn't yet.
run_case pr-branch-analysis-ahead-of-pr "$(jq -nc --arg m "$MAIN_SHA" --arg h "$HEAD_SHA" \
  --argjson e "$(cloud_pr 42 "$OLD_SHA" 2026-11-10T09:50:00+0000)" \
  '{analyses: {main: [$m], "feature/x": [$h]}, pull_requests: [[$e]]}')" "${PR_ENV[@]}"
expect_pending
expect "gives up after 3 polls" count project_pull_requests/list 3
expect "logs the commit the PR analysis is of" logged "(latest analysis is of $OLD_SHA)"

# PR 41 shares the head commit; PR 42's own analysis is a commit behind.
run_case pr-stale-sonarcloud "$(jq -nc --argjson a "$(cloud_pr 41 "$HEAD_SHA" 2026-11-10T10:04:00+0000)" \
  --argjson b "$(cloud_pr 42 "$OLD_SHA" 2026-11-10T09:50:00+0000)" '{pull_requests: [[$a, $b]]}')" "${PR_ENV[@]}"
expect_pending
expect "logs the timeout and the stale commit" \
  logged "pull request 42 analysis for $HEAD_SHA did not appear within 30s (latest analysis is of $OLD_SHA)"

# 11:59+0200 is 09:59Z: the analysis started a minute before the commit existed.
run_case pr-stale-server "$(jq -nc --argjson e "$(server_pr 42 2026-11-10T11:59:00+0200)" \
  '{pull_requests: [[$e]]}')" "${PR_ENV[@]}"
expect_pending
expect "logs the stale analysis date" logged "(latest analysis (2026-11-10T11:59:00+0200) predates 2026-11-10T10:00:00Z)"

run_case pr-pending-then-complete-sonarcloud "$(jq -nc \
  --argjson o "$(cloud_pr 42 "$OLD_SHA" 2026-11-10T09:50:00+0000)" \
  --argjson h "$(cloud_pr 42 "$HEAD_SHA" 2026-11-10T10:04:00+0000)" \
  '{pull_requests: [[], [$o], [$h]]}')" "${PR_ENV[@]}"
expect_pr_complete
expect "polls until the analysis lands (3 polls)" count project_pull_requests/list 3

# 04:59:59-0500 is a second before the commit; 05:00:00-0500 is the commit's second.
run_case pr-pending-then-complete-server "$(jq -nc \
  --argjson o "$(server_pr 42 2026-11-10T04:59:59-0500)" --argjson h "$(server_pr 42 2026-11-10T05:00:00-0500)" \
  '{pull_requests: [[$o], [$h]]}')" "${PR_ENV[@]}"
expect_pr_complete
expect "polls until the analysis lands (2 polls)" count project_pull_requests/list 2

run_case pr-not-analyzed "$(jq -nc --argjson e "$(cloud_pr 41 "$HEAD_SHA" 2026-11-10T10:04:00+0000)" \
  '{pull_requests: [[$e]]}')" "${PR_ENV[@]}"
expect_pending
expect "gives up after 3 polls" count project_pull_requests/list 3
expect "logs that the PR has no analysis" logged "(pull request not analyzed yet)"

run_case pr-api-error '{"pull_requests": [{"status": 500}]}' "${PR_ENV[@]}"
expect_pending
expect "keeps polling through errors (3 polls)" count project_pull_requests/list 3
expect "logs the failed request" logged "(API request failed)"

# Without a checkout there's no commit time, so the analysis must not predate the run.
CWD="$TMP/nogit" run_case pr-server-no-checkout "$(jq -nc --argjson e "$(server_pr 42 2020-01-01T00:00:00+0000)" \
  '{pull_requests: [[$e]]}')" "${PR_ENV[@]}"
expect_pending

run_case pr-no-sha "$(jq -nc --argjson e "$(server_pr 42 2020-01-01T00:00:00+0000)" \
  '{pull_requests: [[$e]]}')" "${PR_ENV[@]}" LUNAR_COMPONENT_GIT_SHA=
expect_pr_complete
expect "checks once" count project_pull_requests/list 1

# --- Skips: no token or no project key means no SonarQube calls and no data.

for c in "no-token LUNAR_SECRET_SONARQUBE_TOKEN=" "no-project-key LUNAR_VAR_PROJECT_KEY="; do
  run_case "${c%% *}" '{}' "${PR_ENV[@]}" "${c#* }"
  expect "exits 0" test "$CODE" -eq 0
  expect "collects nothing" test ! -s "$OUT"
  expect "calls nothing" test ! -s "$REQ"
done

echo
if [ "$FAILED" -gt 0 ]; then
  echo "$FAILED assertion(s) failed"
  exit 1
fi
echo "all passed"
