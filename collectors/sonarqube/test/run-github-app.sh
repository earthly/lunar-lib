#!/bin/bash
# Offline end-to-end test for github-app.sh: the real script, github-app.jq and
# helpers.sh, curl, jq and lunar CLI against test/github_api.py, a GitHub REST
# API stand-in. A curl wrapper sends api.github.com and GHES /api/v3 calls to
# it with the host kept in the path, and a lunar wrapper stands in for
# `lunar github-app get-token`. sleep is stubbed and logged, so a 30s timeout
# at a 10s interval is exactly 4 polls (0, 10, 20 and 30s). The check-run summaries in
# test/fixtures are real SonarQube Cloud, SonarQube Server and community branch
# plugin output with the project renamed (community-failed follows the plugin's
# source).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../github-app.sh"
FIX="$HERE/fixtures"
TMP="$(mktemp -d)"

python3 "$HERE/github_api.py" "$TMP/requests.log" "$TMP/port" > "$TMP/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; rm -rf "$TMP"' EXIT
for _ in $(seq 1 50); do [ -s "$TMP/port" ] && break; sleep 0.1; done
PORT="$(cat "$TMP/port")"

mkdir -p "$TMP/bin" "$TMP/tmp"
printf '#!/bin/sh\necho "$*" >> "%s/sleep.log"\n' "$TMP" > "$TMP/bin/sleep"
cat > "$TMP/bin/curl" <<EOF
#!/bin/bash
args=()
for a in "\$@"; do
  case "\$a" in
    https://api.github.com/*) a="http://127.0.0.1:$PORT/github.com/\${a#https://api.github.com/}" ;;
    https://*) a="http://127.0.0.1:$PORT/\${a#https://}" ;;
  esac
  args+=("\$a")
done
exec $(command -v curl) "\${args[@]}"
EOF
# get-token prints the next of TEST_APP_TOKENS (the last repeating); none fails.
cat > "$TMP/bin/lunar" <<EOF
#!/bin/bash
if [ "\${1:-} \${2:-}" = "github-app get-token" ]; then
  echo "\$*" >> "$TMP/get-token.log"
  IFS=, read -ra tokens <<< "\${TEST_APP_TOKENS:-}"
  n=\$(wc -l < "$TMP/get-token.log")
  [ "\${#tokens[@]}" -gt 0 ] || { echo "Error: no GitHub App installation for this owner" >&2; exit 1; }
  [ "\$n" -le "\${#tokens[@]}" ] || n=\${#tokens[@]}
  echo "\${tokens[\$((n - 1))]}"
  exit 0
fi
exec $(command -v lunar) "\$@"
EOF
chmod +x "$TMP/bin/"*

SHA=1f0e3d4c5b6a79881726354433221100ffeeddcc
OTHER_SHA=2222222222222222222222222222222222222222
CLOUD_URL="https://sonarcloud.io/dashboard?id=acme_widgets&pullRequest=42"
SERVER_URL="https://sonar.example.com/sonarqube/dashboard?id=com.acme%3Awidgets&pullRequest=42"
COMMUNITY_URL="https://sonar.example.com/dashboard?id=acme_widgets&pullRequest=42"
GHES=(LUNAR_COMPONENT_ID=ghes.example.com/acme/widgets LUNAR_SECRET_GH_ENTERPRISE_TOKEN=ghes-token)

# check <fixture|-> [name] [details_url] [status] [id] [app] [head_sha]: a check
# run as GitHub lists it. "-" is a check with no output, for decoys.
check() {
  local fixture="$1" name="${2:-SonarQube Code Analysis}" url="${3:-$SERVER_URL}" status="${4:-completed}"
  local id="${5:-100}" app="${6:-sonarqube}" sha="${7:-$SHA}" src='{"conclusion": "success"}'
  [ "$fixture" = "-" ] || src="$(cat "$FIX/$fixture.json")"
  printf '%s' "$src" | jq -c --arg name "$name" --arg url "$url" --arg status "$status" --argjson id "$id" \
    --arg app "$app" --arg sha "$sha" '
    {id: $id, name: $name, head_sha: $sha, status: $status, details_url: $url, app: {slug: $app}}
    + if $status == "completed"
      then {conclusion, completed_at: "2026-11-10T10:04:00Z", output: {title, summary}}
      else {conclusion: null, completed_at: null, output: {title: null, summary: null}} end'
}
# polls <poll JSON>...: a scenario serving one poll after another.
polls() { jq -cn '{polls: [$ARGS.positional[] | fromjson]}' --args "$@"; }
one() { printf '[%s]' "$(IFS=,; echo "$*")"; }

FAILED=0
CASE=""

# run_case <name> <scenario> [VAR=value ...]: loads the scenario into the
# stand-in and runs github-app.sh in a clean env, as the PR code hook would,
# killing a run that hangs (exit 124). Leaves the merged Component JSON in $CJ,
# requests in $REQ.
run_case() {
  CASE="$1"; printf '%s' "$2" > "$TMP/$CASE.scenario.json"; shift 2
  curl -fsS "http://127.0.0.1:$PORT/__load?file=$TMP/$CASE.scenario.json" > /dev/null
  rm -f "$TMP/get-token.log" "$TMP/sleep.log"
  OUT="$TMP/$CASE.out"; ERR="$TMP/$CASE.err"; CJ="$TMP/$CASE.json"; REQ="$TMP/$CASE.requests"
  (cd "$TMP" && env -i PATH="$TMP/bin:$PATH" HOME="$TMP" TMPDIR="$TMP/tmp" \
    LUNAR_COLLECT_STDOUT=1 \
    LUNAR_COMPONENT_ID=github.com/acme/widgets \
    LUNAR_COMPONENT_GIT_SHA="$SHA" \
    LUNAR_COMPONENT_PR=42 \
    LUNAR_SECRET_GH_TOKEN=gh-token \
    LUNAR_VAR_GITHUB_APP_POLL_TIMEOUT_SECONDS=30 \
    LUNAR_VAR_GITHUB_APP_POLL_INTERVAL_SECONDS=10 \
    "$@" timeout 60 bash "$SCRIPT" > "$OUT" 2> "$ERR")
  CODE=$?
  cp "$TMP/requests.log" "$REQ"
  touch "$TMP/get-token.log" "$TMP/sleep.log"
  cp "$TMP/get-token.log" "$TMP/$CASE.get-token"
  SLEPT="$(paste -sd' ' "$TMP/sleep.log")"
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
polled() { count 'page=1 ' "$1"; }

expect_complete() { # expect_complete <passing> <gate status>
  expect "exits 0" test "$CODE" -eq 0
  expect "records the check run as complete" cj '.code_quality.native.sonarqube.github_app.status == "complete"'
  expect "writes passing=$1 and gate $2" \
    cj ".code_quality.passing == $1 and .code_quality.native.sonarqube.quality_gate.status == \"$2\""
}
expect_pending() {
  expect "exits 0" test "$CODE" -eq 0
  expect "writes status pending and nothing else" \
    cj '. == {code_quality: {native: {sonarqube: {github_app: {status: "pending"}}}}}'
}
expect_error() {
  expect "exits 1" test "$CODE" -eq 1
  expect "collects nothing" test ! -s "$OUT"
}
expect_skip() {
  expect "exits 0" test "$CODE" -eq 0
  expect "collects nothing" test ! -s "$OUT"
  expect "calls nothing" test ! -s "$REQ"
}

# --- github.com + SonarQube Cloud.

run_case cloud-passed "$(polls "$(one "$(check cloud-passed "SonarCloud Code Analysis" "$CLOUD_URL" completed 100 sonarqubecloud)")")"
expect_complete true OK
expect "reads github.com's API with GH_TOKEN, all check runs, on the first poll" \
  count "^github\.com /repos/acme/widgets/commits/$SHA/check-runs\?filter=all&per_page=100&page=1 gh-token$" 1
expect "records the check run" cj '.code_quality.native.sonarqube.github_app.check_runs == [{
    name: "SonarCloud Code Analysis", project_key: "acme_widgets", conclusion: "success", title: "Quality Gate passed",
    url: "https://sonarcloud.io/dashboard?id=acme_widgets&pullRequest=42", completed_at: "2026-11-10T10:04:00Z", quality_gate: "passed"}]'
expect "writes conditions_failed 0" cj '.code_quality.native.sonarqube.quality_gate == {status: "OK", conditions_failed: 0}'
expect "writes the PR's new-code numbers, zeros included" cj '.code_quality.pr == {new_issues: 0, accepted_issues: 0,
    security_hotspots: 0, coverage_percentage: 0, duplication_percentage: 0}'
expect "takes the project key and server from the check" cj '.code_quality.source == {tool: "sonarqube",
    integration: "github_app", project_key: "acme_widgets", api_url: "https://sonarcloud.io"}'
expect "writes none of the overall metrics" cj '.code_quality | has("coverage_percentage") or has("duplication_percentage") or has("issues") | not'

run_case cloud-failed "$(polls "$(one "$(check cloud-failed "SonarCloud Code Analysis" "$CLOUD_URL" completed 100 sonarqubecloud)")")"
expect_complete false ERROR
expect "lists the failed conditions" cj '.code_quality.native.sonarqube.quality_gate | .conditions_failed == 2 and .failed_conditions == [
    {text: "57.1% Coverage on New Code (required ≥ 80%)", metric: "Coverage on New Code", value: "57.1%", required: "≥ 80%", project_key: "acme_widgets"},
    {text: "4.5% Duplication on New Code (required ≤ 3%)", metric: "Duplication on New Code", value: "4.5%", required: "≤ 3%", project_key: "acme_widgets"}]'
expect "writes only the numbers the failed summary shows" cj '.code_quality.pr == {coverage_percentage: 57.1, duplication_percentage: 4.5}'

run_case cloud-failed-ratings "$(polls "$(one "$(check cloud-failed-ratings "SonarCloud Code Analysis" "$CLOUD_URL" completed 100 sonarqubecloud)")")"
expect_complete false ERROR
expect "lists the rating conditions" cj '[.code_quality.native.sonarqube.quality_gate.failed_conditions[] | [.value, .metric, .required]]
    == [["C", "Security Rating on New Code", "≥ A"], ["D", "Reliability Rating on New Code", "≥ A"]]'
expect "writes no new-code numbers" cj '.code_quality | has("pr") | not'

run_case cloud-analysis-failed "$(polls "$(one "$(check cloud-analysis-failed "SonarCloud Code Analysis" "$CLOUD_URL" completed 100 sonarqubecloud)")")"
expect "exits 0" test "$CODE" -eq 0
expect "records the failed analysis, without a gate" cj '.code_quality.native.sonarqube.github_app.check_runs[0]
    | .conclusion == "cancelled" and .title == "SonarQube Cloud analysis failed" and (has("quality_gate") | not)'
expect "writes no passing, gate or numbers" cj '(.code_quality | has("passing") or has("pr") | not)
    and (.code_quality.native.sonarqube | has("quality_gate") | not)'

# --- GitHub Enterprise Server + SonarQube Server.

run_case ghes-server-passed "$(polls "$(one "$(check server-passed)")")" "${GHES[@]}"
expect_complete true OK
expect "reads the GHES host's /api/v3 with GH_ENTERPRISE_TOKEN" \
  count "^ghes\.example\.com /api/v3/repos/acme/widgets/commits/$SHA/check-runs\?filter=all&per_page=100&page=1 ghes-token$" 1
expect "never calls github.com" count '^github\.com ' 0
expect "writes the new-code numbers, fixed issues included" cj '.code_quality.pr == {new_issues: 0, fixed_issues: 1,
    accepted_issues: 0, security_hotspots: 0, coverage_percentage: 94.3, duplication_percentage: 0}'
expect "decodes the project key and keeps the server's context path" \
  cj '.code_quality.source | .project_key == "com.acme:widgets" and .api_url == "https://sonar.example.com/sonarqube"'

run_case ghes-server-no-coverage "$(polls "$(one "$(check server-passed-no-coverage)")")" "${GHES[@]}"
expect_complete true OK
expect "leaves coverage absent for 'No data about Coverage', not 0" cj '.code_quality.pr == {new_issues: 0, fixed_issues: 0,
    accepted_issues: 0, security_hotspots: 0, duplication_percentage: 0}'

run_case ghes-server-failed "$(polls "$(one "$(check server-failed)")")" "${GHES[@]}"
expect_complete false ERROR
expect "lists a condition with no threshold" cj '.code_quality.native.sonarqube.quality_gate | .conditions_failed == 1
    and .failed_conditions == [{text: "2 New issues", metric: "New issues", value: "2", project_key: "com.acme:widgets"}]'
expect "writes the new-issue count from the condition" cj '.code_quality.pr == {new_issues: 2}'

run_case ghes-server-dependency-risk "$(polls "$(one "$(check server-failed-dependency-risk)")")" "${GHES[@]}"
expect_complete false ERROR
expect "keeps a condition without a value" cj '.code_quality.native.sonarqube.quality_gate.failed_conditions == [{
    text: "Vulnerability dependency risks too severe (required < '"'"'medium'"'"' severity)",
    metric: "Vulnerability dependency risks too severe", required: "< '"'"'medium'"'"' severity", project_key: "com.acme:widgets"}]'

run_case ghes-gh-token-fallback "$(polls "$(one "$(check server-passed)")")" \
  LUNAR_COMPONENT_ID=ghes.example.com/acme/widgets
expect_complete true OK
expect "falls back to GH_TOKEN on GHES" count '^ghes\.example\.com /api/v3/.* gh-token$' 1

run_case ghes-monorepo-component "$(polls "$(one "$(check server-passed)")")" \
  LUNAR_COMPONENT_ID=ghes.example.com/acme/widgets/services/api LUNAR_SECRET_GH_ENTERPRISE_TOKEN=ghes-token
expect_complete true OK
expect "drops the component's subpath from the repository" count "^ghes\.example\.com /api/v3/repos/acme/widgets/commits/" 1

# --- The community branch plugin's layout.

run_case community-passed "$(polls "$(one "$(check community-passed SonarQube\ Code\ Analysis "$COMMUNITY_URL")")")"
expect_complete true OK
expect "reads 'Quality Gate success' as passed, and an after-merge estimate as no new-code data" \
  cj '.code_quality.pr == {new_issues: 0, fixed_issues: 0, accepted_issues: 0, security_hotspots: 0}'

run_case community-failed "$(polls "$(one "$(check community-failed SonarQube\ Code\ Analysis "$COMMUNITY_URL")")")"
expect_complete false ERROR
expect "lists its conditions" cj '[.code_quality.native.sonarqube.quality_gate.failed_conditions[] | [.value, .metric]]
    == [["45.00%", "Coverage on New Code"], ["4.50%", "Duplicated Lines (%) on New Code"], ["C", "Reliability Rating on New Code"], ["3", "New Issues"]]
    and .code_quality.native.sonarqube.quality_gate.conditions_failed == 4'
expect "writes the numbers from its conditions" \
  cj '.code_quality.pr == {new_issues: 3, coverage_percentage: 45, duplication_percentage: 4.5}'

# --- The gate comes from SonarQube's title; the conclusion only when that's unknown.

run_case non-blocking-failed-gate "$(polls "$(one "$(check server-failed | jq -c '.conclusion = "neutral"')")")"
expect_complete false ERROR
expect "reads a failed gate on a neutral check as failed" cj '.code_quality.native.sonarqube.github_app.check_runs[0]
    | .conclusion == "neutral" and .quality_gate == "failed"'

run_case non-blocking-passed-gate "$(polls "$(one "$(check server-passed | jq -c '.conclusion = "neutral"')")")"
expect_complete true OK

run_case unreadable-failed-summary "$(polls "$(one "$(check server-failed | jq -c '.output.summary = "Something else entirely"')")")"
expect_complete false ERROR
expect "claims no condition count or list it couldn't read" cj '.code_quality.native.sonarqube.quality_gate == {status: "ERROR"}'
expect "writes no numbers" cj '.code_quality | has("pr") | not'

run_case unknown-title "$(polls "$(one "$(check server-passed | jq -c '.output.title = "Analysis complete"')")")"
expect_complete true OK

# --- Polling: SonarQube posts the check only after its analysis.

run_case appears-then-completes "$(polls '[]' \
  "$(one "$(check - SonarQube\ Code\ Analysis "$SERVER_URL" in_progress)")" \
  "$(one "$(check server-passed)")")"
expect_complete true OK
expect "polls until the check run completes (3 polls)" polled 3

run_case timeout "$(polls '[]')"
expect_pending
expect "polls at 0, 10, 20 and 30s, then gives up" polled 4
expect "sleeps between polls only" test "$SLEPT" = "10 10 10"
expect "logs why" logged "no completed SonarQube check run for pull request 42 on $SHA within 30s (no SonarQube check run on the commit yet)"

run_case timeout-in-progress "$(polls "$(one "$(check - SonarQube\ Code\ Analysis "$SERVER_URL" queued)")")"
expect_pending
expect "logs the check run still running" logged "(SonarQube Code Analysis is queued)"

run_case zero-timeout "$(polls "$(one "$(check server-passed)")")" LUNAR_VAR_GITHUB_APP_POLL_TIMEOUT_SECONDS=0
expect_complete true OK
expect "polls once" polled 1

# --- Commit and pull request association.

run_case branch-analysis-only "$(polls "$(one "$(check server-failed SonarQube\ Code\ Analysis \
  "https://sonar.example.com/sonarqube/dashboard?id=com.acme%3Awidgets&branch=main")")")"
expect_pending
expect "ignores a branch analysis of the same commit" logged "(the SonarQube check runs on the commit are for branch main, not pull request 42)"

run_case other-pull-request "$(polls "$(one "$(check server-passed SonarQube\ Code\ Analysis "${SERVER_URL%42}41")")")"
expect_pending
expect "ignores another pull request's analysis of the same commit" logged "are for pull request 41, not pull request 42)"

run_case other-commit "$(polls "$(one "$(check server-passed SonarQube\ Code\ Analysis "$SERVER_URL" completed 100 sonarqube "$OTHER_SHA")")")"
expect_pending
expect "ignores a check run on another commit" logged "(no SonarQube check run on the commit yet)"

# A later branch analysis shares the name; filter=all still lists the PR's run.
run_case pr-and-branch-same-name "$(polls "$(one "$(check server-passed SonarQube\ Code\ Analysis "$SERVER_URL" completed 100)" \
  "$(check server-failed SonarQube\ Code\ Analysis "${SERVER_URL%pullRequest=42}branch=main" completed 101)")")"
expect_complete true OK

run_case rerun-newest-wins "$(polls "$(one "$(check server-passed SonarQube\ Code\ Analysis "$SERVER_URL" completed 100)" \
  "$(check server-failed SonarQube\ Code\ Analysis "$SERVER_URL" completed 101)")")"
expect_complete false ERROR
expect "reads only the newest run" cj '.code_quality.native.sonarqube.github_app.check_runs | length == 1'

run_case rerun-in-progress "$(polls \
  "$(one "$(check server-passed SonarQube\ Code\ Analysis "$SERVER_URL" completed 100)" "$(check - SonarQube\ Code\ Analysis "$SERVER_URL" in_progress 101)")" \
  "$(one "$(check server-passed SonarQube\ Code\ Analysis "$SERVER_URL" completed 100)" "$(check server-failed SonarQube\ Code\ Analysis "$SERVER_URL" completed 101)")")"
expect_complete false ERROR
expect "waits for the re-run instead of reading the older result (2 polls)" polled 2

run_case decoys "$(polls "$(one \
  "$(check - "SonarCloud Code Analysis" "https://github.com/acme/widgets/actions/runs/1/job/2" completed 1 github-actions)" \
  "$(check - "SonarCloud (frontend)" "https://github.com/acme/widgets/actions/runs/1/job/3" completed 2 github-actions)" \
  "$(check - "SonarCloud" "https://github.com/acme/widgets/runs/4" completed 3 github-advanced-security)" \
  "$(check - "SonarQube Code Analysis" "https://ci.example.com/job/sonar/5/" completed 4 jenkins)")")"
expect_pending
expect "ignores CI jobs and code-scanning checks named after SonarQube" logged "(no SonarQube check run on the commit yet)"

# --- Several SonarQube projects on one repository.

MONO_A="https://sonar.example.com/sonarqube/dashboard?id=acme_api&pullRequest=42"
MONO_B="https://sonar.example.com/sonarqube/dashboard?id=acme_web&pullRequest=42"
MONO="$(polls "$(one "$(check server-passed "[api] SonarQube Code Analysis" "$MONO_A" completed 100)" \
  "$(check cloud-failed "[web] SonarQube Code Analysis" "$MONO_B" completed 101)")")"

run_case monorepo-project-key "$MONO" LUNAR_VAR_PROJECT_KEY=acme_api
expect_complete true OK
expect "reads only the configured project" cj '.code_quality.native.sonarqube.github_app.check_runs | map(.project_key) == ["acme_api"]'
expect "writes that project's numbers" cj '.code_quality.pr.coverage_percentage == 94.3 and .code_quality.source.project_key == "acme_api"'

run_case monorepo-meta-key "$MONO" LUNAR_COMPONENT_META='{"sonarqube/project-key":"acme_web"}'
expect_complete false ERROR
expect "reads the project from the catalog meta" cj '.code_quality.native.sonarqube.github_app.check_runs | map(.project_key) == ["acme_web"]'

run_case monorepo-no-key "$MONO"
expect_complete false ERROR
expect "reads every project's check" cj '.code_quality.native.sonarqube.github_app.check_runs | map(.project_key) == ["acme_api", "acme_web"]'
expect "tags each failed condition with its project" cj '.code_quality.native.sonarqube.quality_gate | .conditions_failed == 2
    and (.failed_conditions | map(.project_key) | unique == ["acme_web"])'
expect "writes no single-project numbers or key" cj '(.code_quality | has("pr") | not) and (.code_quality.source | has("project_key") | not)'

run_case monorepo-key-not-reported "$MONO" LUNAR_VAR_PROJECT_KEY=acme_jobs
expect_pending
expect "logs the projects that did report" logged "(no SonarQube check run for project acme_jobs (found acme_api, acme_web))"

# --- Pagination: 150 other check runs ahead of SonarQube's.

MANY="$(for i in $(seq 1 150); do check - "build ($i)" "https://github.com/acme/widgets/actions/runs/1/job/$i" completed "$i" github-actions; done | jq -cs .)"
run_case second-page "$(polls "$(jq -c --argjson s "$(check server-passed SonarQube\ Code\ Analysis "$SERVER_URL" completed 500)" '. + [$s]' <<< "$MANY")")"
expect_complete true OK
expect "reads both pages" count 'page=2 ' 1

# --- Errors: retry what's transient, fail on the rest.

run_case server-error-then-ok "$(polls '{"status": 502}' "$(one "$(check server-passed)")")"
expect_complete true OK
expect "retries after a 502 (2 polls)" polled 2

run_case rate-limited-then-ok "$(polls '{"status": 403, "message": "API rate limit exceeded for installation"}' "$(one "$(check server-passed)")")"
expect_complete true OK
expect "retries after a rate-limit 403 (2 polls)" polled 2

run_case github-down "$(polls '{"status": 503}')"
expect_error
expect "polls the whole wait (4 polls)" polled 4
expect "logs the failure" logged "GitHub didn't answer within 30s (HTTP 503 from https://api.github.com/repos/acme/widgets/commits/$SHA/check-runs: simulated failure)"

run_case bad-credentials "$(polls '{"status": 401, "message": "Bad credentials"}')"
expect_error
expect "doesn't retry" polled 1
expect "logs the GitHub error" logged "HTTP 401 from https://api.github.com/repos/acme/widgets/commits/$SHA/check-runs: Bad credentials"

run_case forbidden "$(polls '{"status": 403, "message": "Resource not accessible by integration"}')"
expect_error
expect "doesn't retry" polled 1

run_case not-found "$(polls '{"status": 404, "message": "Not Found"}')"
expect_error
expect "doesn't retry" polled 1

# --- GitHub App tokens.

run_case app-token "$(polls "$(one "$(check server-passed)")")" LUNAR_VAR_GITHUB_APP=lunar-lib TEST_APP_TOKENS=app-token
expect_complete true OK
expect "asks the App for read access to checks only" grep -qx 'github-app get-token lunar-lib --permission checks=read' "$TMP/$CASE.get-token"
expect "uses the App's token" count ' app-token$' 1
expect "logs the auth source" logged "GitHub auth: GitHub App lunar-lib"

run_case app-token-ghes "$(polls "$(one "$(check server-passed)")")" "${GHES[@]}" LUNAR_VAR_GITHUB_APP=lunar-lib TEST_APP_TOKENS=app-token
expect_complete true OK
expect "uses the App's token on GHES over GH_ENTERPRISE_TOKEN" count '^ghes\.example\.com /api/v3/.* app-token$' 1

run_case app-token-fallback "$(polls "$(one "$(check server-passed)")")" LUNAR_VAR_GITHUB_APP=lunar-lib
expect_complete true OK
expect "falls back to GH_TOKEN" count ' gh-token$' 1
expect "logs the fallback" logged "GitHub auth: GH_TOKEN secret, because GitHub App lunar-lib minted no token"

run_case app-only-no-token "$(polls "$(one "$(check server-passed)")")" LUNAR_VAR_GITHUB_APP=lunar-lib LUNAR_VAR_GITHUB_APP_ONLY=true
expect_error
expect "calls nothing" test ! -s "$REQ"

run_case app-token-expires "$(polls '[]' '{"status": 401, "message": "Bad credentials"}' "$(one "$(check server-passed)")")" \
  LUNAR_VAR_GITHUB_APP=lunar-lib TEST_APP_TOKENS=app-token,app-token-2
expect_complete true OK
expect "mints a new token after a 401 and carries on" count ' app-token-2$' 1
expect "mints twice" test "$(wc -l < "$TMP/$CASE.get-token")" -eq 2

run_case app-token-revoked "$(polls '[]' '{"status": 401, "message": "Bad credentials"}')" \
  LUNAR_VAR_GITHUB_APP=lunar-lib TEST_APP_TOKENS=app-token,app-token-2
expect_error
expect "mints once more, then fails on the second 401 (3 polls)" polled 3
expect "logs the GitHub error" logged "HTTP 401 from https://api.github.com/repos/acme/widgets/commits/$SHA/check-runs: Bad credentials"

# --- Skips and bad input: no GitHub calls.

for c in "not-a-pr LUNAR_COMPONENT_PR=" "no-sha LUNAR_COMPONENT_GIT_SHA=" "no-token LUNAR_SECRET_GH_TOKEN=" \
         "bad-component-id LUNAR_COMPONENT_ID=widgets"; do
  run_case "${c%% *}" "$(polls '[]')" "${c#* }"
  expect_skip
done
run_case ghes-no-token "$(polls '[]')" LUNAR_COMPONENT_ID=ghes.example.com/acme/widgets LUNAR_SECRET_GH_TOKEN=
expect_skip
expect "names the GHES secret" logged "no GH_ENTERPRISE_TOKEN (or GH_TOKEN) secret for ghes.example.com"

run_case bad-timeout "$(polls '[]')" LUNAR_VAR_GITHUB_APP_POLL_TIMEOUT_SECONDS=3m
expect_error
expect "calls nothing" test ! -s "$REQ"

run_case zero-interval "$(polls '[]')" LUNAR_VAR_GITHUB_APP_POLL_INTERVAL_SECONDS=00
expect_error
expect "calls nothing" test ! -s "$REQ"

run_case leading-zeros "$(polls '[]')" LUNAR_VAR_GITHUB_APP_POLL_TIMEOUT_SECONDS=030 LUNAR_VAR_GITHUB_APP_POLL_INTERVAL_SECONDS=08
expect_pending
expect "reads 030 and 08 as decimal, the last poll at the deadline (0, 8, 16, 24, 30s)" test "$SLEPT" = "8 8 8 6"
expect "polls 5 times" polled 5

echo
if [ "$FAILED" -gt 0 ]; then
  echo "$FAILED assertion(s) failed"
  exit 1
fi
echo "all passed"
