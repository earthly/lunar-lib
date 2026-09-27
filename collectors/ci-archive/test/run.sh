#!/bin/bash
# Offline end-to-end test for backup-logs-s3.sh (and the archive-run.sh it hands
# off to): the real scripts, curl, jq, python3 and lunar CLI against the
# stand-ins in servers.py. The component is GHES-shaped
# (127.0.0.1:8443/acme/widgets), so the /api/v3 path is exercised without any
# test-only switch in the script.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../backup-logs-s3.sh"
TMP="$(mktemp -d)"
export S3_DIR="$TMP/s3" STS_LOG="$TMP/sts.log"
mkdir -p "$S3_DIR"

openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=127.0.0.1" \
  -addext "subjectAltName=IP:127.0.0.1" \
  -keyout "$TMP/key.pem" -out "$TMP/cert.pem" 2>/dev/null
python3 "$HERE/servers.py" "$TMP/cert.pem" "$TMP/key.pem" > "$TMP/servers.log" 2>&1 &
SERVERS=$!
trap 'kill $SERVERS 2>/dev/null; rm -rf "$TMP"' EXIT
for _ in $(seq 1 50); do grep -q ready "$TMP/servers.log" && break; sleep 0.1; done

FAILED=0
CASE=""

# run_case <name> <run-id> <attempt> [VAR=value ...]: runs the collector in a
# clean env, as the Hub's after-ci-pipeline hook would for that run attempt.
run_case() {
  CASE="$1"; local run_id="$2" attempt="$3"; shift 3
  OUT="$TMP/$CASE.out"; ERR="$TMP/$CASE.err"
  env -i PATH="$PATH" HOME="$TMP" \
    CURL_CA_BUNDLE="$TMP/cert.pem" \
    LUNAR_COLLECT_STDOUT=1 \
    LUNAR_COMPONENT_ID=127.0.0.1:8443/acme/widgets \
    LUNAR_COMPONENT_GIT_SHA="sha-$run_id" \
    LUNAR_CI_PIPELINE_RUN_ID="$run_id" \
    LUNAR_CI_PIPELINE_RUN_ATTEMPT="$attempt" \
    LUNAR_CI_PIPELINE_NAME=build \
    LUNAR_SECRET_GH_TOKEN=test-gh-token \
    LUNAR_VAR_S3_BUCKET=archive \
    LUNAR_VAR_S3_ENDPOINT_URL=http://127.0.0.1:9001 \
    LUNAR_SECRET_AWS_ACCESS_KEY_ID=AKIATEST \
    LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=secret-test \
    "$@" bash "$SCRIPT" > "$OUT" 2> "$ERR"
  CODE=$?
}

pass() { echo "ok   [$CASE] $1"; }
fail() {
  echo "FAIL [$CASE] $1"
  sed 's/^/       stderr: /' "$ERR"
  FAILED=$((FAILED + 1))
}
expect() { # expect <description> <command...>
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc"; fi
}
expect_exit() { if [ "$CODE" -eq "$1" ]; then pass "exits $1"; else fail "exits $1 (got $CODE)"; fi; }
receipt() { jq -e "$1" "$OUT"; }
stderr_has() { grep -q -- "$1" "$ERR"; }
stderr_lacks() { ! grep -q -- "$1" "$ERR"; }
nothing_collected() { [ ! -s "$OUT" ]; }
no_bucket() { [ ! -e "$S3_DIR/$1" ]; }
object_path() { echo "$S3_DIR/$(jq -r '.ci.archive.runs[0] | .bucket + "/" + .key' "$OUT")"; }
zip_names() { python3 -c 'import sys, zipfile; print("\n".join(sorted(zipfile.ZipFile(sys.argv[1]).namelist())))' "$1"; }

# --- The attempt the hook fired for ---
run_case attempt-1 101 1
expect_exit 0
expect "records one run entry" receipt '.ci.archive.runs | length == 1'
expect "records the attempt it fired for" receipt '.ci.archive.runs[0] | .id == 101 and .attempt == 1 and .name == "build" and .conclusion == "failure"'
expect "keys the object by run and attempt" receipt '.ci.archive.runs[0].uri == "s3://archive/lunar/ci-archive/127.0.0.1_8443/acme/widgets/sha-101/101-1.zip"'
expect "records sizes and jobs" receipt '.ci.archive.runs[0] | .size_bytes > 0 and .log_bytes > 0 and (.jobs | length) == 2'
expect "counts the jobs' log lines, not the per-step copies" receipt '.ci.archive.runs[0].log_lines == 1'
expect "stamps the after-ci-pipeline source" receipt '.ci.archive.runs[0].source | .tool == "ci-archive" and .integration == "after-ci-pipeline" and (has("archived_by") | not)'
OBJ="$(object_path)"
expect "uploads the object to S3" test -s "$OBJ"
expect "object holds manifest.json and the attempt's logs.zip" test "$(zip_names "$OBJ" | tr '\n' ' ')" = "logs.zip manifest.json "
expect "the logs are that attempt's" python3 -c '
import io, sys, zipfile
inner = zipfile.ZipFile(io.BytesIO(zipfile.ZipFile(sys.argv[1]).read("logs.zip")))
assert b"run 101 attempt 1" in inner.read("1_build.txt")
' "$OBJ"
expect "manifest.json matches the receipt" python3 -c '
import json, sys, zipfile
m = json.loads(zipfile.ZipFile(sys.argv[1]).read("manifest.json"))
r = json.load(open(sys.argv[2]))["ci"]["archive"]["runs"][0]
assert m["sha"] == "sha-101" and m["repository"] == "acme/widgets"
assert {k: r[k] for k in m["run"]} == m["run"]
' "$OBJ" "$OUT"

# --- A re-run is its own attempt: its own object and entry ---
run_case attempt-2 101 2
expect_exit 0
expect "records the re-run" receipt '.ci.archive.runs[0] | .attempt == 2 and .conclusion == "success"'
expect "uploads it beside attempt 1" test -s "$S3_DIR/archive/lunar/ci-archive/127.0.0.1_8443/acme/widgets/sha-101/101-2.zip"
expect "leaves attempt 1's object alone" test -s "$OBJ"

# --- A run another workflow started: filed under the commit its chain began at ---
# GitHub recorded run 101 at sha-101 (main's head when it started); the Hub fired
# the collector for origin-sha, where the chain started.
run_case chained 101 1 LUNAR_COMPONENT_GIT_SHA=origin-sha LUNAR_CI_PIPELINE_HEAD_SHA=sha-101 \
  LUNAR_CI_PIPELINE_TRIGGERED_BY_RUN_ID=90 LUNAR_CI_PIPELINE_ORIGIN_SOURCE=tracer
expect_exit 0
expect "keys the object by the chain's commit" receipt '.ci.archive.runs[0].uri == "s3://archive/lunar/ci-archive/127.0.0.1_8443/acme/widgets/origin-sha/101-1.zip"'
expect "records GitHub's commit and the run that started it" receipt '.ci.archive.runs[0] | .head_sha == "sha-101" and .triggered_by_run_id == "90" and .origin_source == "tracer"'
expect "manifest.json names the chain's commit" python3 -c '
import json, sys, zipfile
m = json.loads(zipfile.ZipFile(sys.argv[1]).read("manifest.json"))
assert m["sha"] == "origin-sha" and m["run"]["head_sha"] == "sha-101"
' "$(object_path)"
run_case not-chained 101 1
expect "a run nothing started carries no chain" receipt '.ci.archive.runs[0] | .head_sha == "sha-101" and (has("triggered_by_run_id") or has("origin_source") | not)'

# --- Not configured, or not an after-ci-pipeline run: exit 0, write nothing ---
run_case no-run 101 1 LUNAR_CI_PIPELINE_RUN_ID=
expect_exit 0
expect "writes nothing without a run in context" nothing_collected
expect "says why" stderr_has "no workflow run in context"

# --- No s3_bucket: record the run and count its log lines, upload nothing ---
objects_before=$(find "$S3_DIR" -type f | wc -l)
run_case no-bucket 101 1 LUNAR_VAR_S3_BUCKET= LUNAR_VAR_S3_ENDPOINT_URL= \
  LUNAR_SECRET_AWS_ACCESS_KEY_ID= LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=
expect_exit 0
expect "records the run without AWS credentials" receipt '.ci.archive.runs[0] | .id == 101 and .attempt == 1 and .log_lines == 1 and .log_bytes > 0 and (.jobs | length) == 2'
expect "records no storage location" receipt '.ci.archive.runs[0] | (has("uri") or has("bucket") or has("key") or has("size_bytes")) | not'
expect "uploads nothing" test "$(find "$S3_DIR" -type f | wc -l)" -eq "$objects_before"
expect "says why" stderr_has "s3_bucket is not set"

run_case no-token 101 1 LUNAR_SECRET_GH_TOKEN=
expect_exit 0
expect "writes nothing without GH_TOKEN" nothing_collected
expect "says why" stderr_has "GH_TOKEN secret is not set"

run_case filtered-out 101 1 'LUNAR_VAR_INCLUDE_RUNS_PATTERN=^deploy$'
expect_exit 0
expect "skips a workflow include_runs_pattern leaves out" nothing_collected
expect "says why" stderr_has "does not match include_runs_pattern"

run_case filtered-in 101 1 'LUNAR_VAR_INCLUDE_RUNS_PATTERN=^(build|deploy)$'
expect_exit 0
expect "archives a workflow include_runs_pattern matches" receipt '.ci.archive.runs[0].id == 101'

# Run 601 was started by workflow_run, run 101 by push.
run_case event-left-out 601 1 LUNAR_VAR_INCLUDE_EVENTS=push
expect_exit 0
expect "skips a run triggered by an event include_events leaves out" nothing_collected
expect "says why" stderr_has "triggered by workflow_run, not one of the included events"

run_case event-listed 101 1 'LUNAR_VAR_INCLUDE_EVENTS=pull_request, push'
expect_exit 0
expect "archives a run triggered by a listed event" receipt '.ci.archive.runs[0] | .id == 101 and .event == "push"'

run_case all-events 601 1
expect_exit 0
expect "archives every event when include_events is empty" receipt '.ci.archive.runs[0] | .id == 601 and .event == "workflow_run"'

# --- A bucket in another account: upload as a role there ---
# ingress* buckets take only the credentials STS hands out for ROLE, and only
# with EXTERNAL_ID (servers.py).
ROLE=arn:aws:iam::111122223333:role/ci-archive-ingress
EXTERNAL_ID='lunar-ext=test+1'
STS=AWS_ENDPOINT_URL_STS=http://127.0.0.1:9002

# Control arm: the base keys alone are refused, so assume-role below can only
# pass by uploading as the role.
run_case ingress-base-keys 101 1 "$STS" LUNAR_VAR_S3_BUCKET=ingress-base
expect_exit 1
expect "the base keys can't write to the other account's bucket" stderr_has "AccessDenied"
expect "uploads nothing" no_bucket ingress-base

run_case assume-role 101 1 "$STS" LUNAR_VAR_S3_BUCKET=ingress-ok \
  LUNAR_VAR_AWS_ASSUME_ROLE_ARNS="$ROLE" LUNAR_VAR_AWS_EXTERNAL_ID="$EXTERNAL_ID"
expect_exit 0
expect "uploads as the assumed role" test -s "$S3_DIR/ingress-ok/lunar/ci-archive/127.0.0.1_8443/acme/widgets/sha-101/101-1.zip"
expect "records the upload" receipt '.ci.archive.runs[0].uri == "s3://ingress-ok/lunar/ci-archive/127.0.0.1_8443/acme/widgets/sha-101/101-1.zip"'
expect "says where the credentials came from" stderr_has "credentials from static-keys+assume-role"
expect "names the STS session after the run attempt" grep -qx "lunar-ci-archive-101-1" "$STS_LOG"

# Control arm: temporary keys are refused without their session token, so the
# next case proves the token was sent and signed.
run_case temp-base-no-token 101 2 "$STS" LUNAR_VAR_S3_BUCKET=ingress-notoken \
  LUNAR_VAR_AWS_ASSUME_ROLE_ARNS="$ROLE" LUNAR_VAR_AWS_EXTERNAL_ID="$EXTERNAL_ID" \
  LUNAR_SECRET_AWS_ACCESS_KEY_ID=ASIABASETEST LUNAR_SECRET_AWS_SECRET_ACCESS_KEY='base/Secret+test'
expect_exit 1
expect "STS refuses temporary keys sent without their token" stderr_has "role 1/1 not assumed (InvalidToken)"
expect "uploads nothing" no_bucket ingress-notoken

run_case assume-role-temp-base 101 2 "$STS" LUNAR_VAR_S3_BUCKET=ingress-temp \
  LUNAR_VAR_AWS_ASSUME_ROLE_ARNS="$ROLE" LUNAR_VAR_AWS_EXTERNAL_ID="$EXTERNAL_ID" \
  LUNAR_SECRET_AWS_ACCESS_KEY_ID=ASIABASETEST LUNAR_SECRET_AWS_SECRET_ACCESS_KEY='base/Secret+test' \
  LUNAR_SECRET_AWS_SESSION_TOKEN='IQoJb3JpZ2luX2VjE+base/session/token=='
expect_exit 0
expect "chains from temporary base credentials, session token signed" receipt '.ci.archive.runs[0].attempt == 2'

run_case assume-role-order 101 1 "$STS" LUNAR_VAR_S3_BUCKET=ingress-order \
  LUNAR_VAR_AWS_ASSUME_ROLE_ARNS="arn:aws:iam::111122223333:role/elsewhere, $ROLE" \
  LUNAR_VAR_AWS_EXTERNAL_ID="$EXTERNAL_ID"
expect_exit 0
expect "moves past a role STS refuses" stderr_has "role 1/2 not assumed (AccessDenied)"
expect "uploads as the next role" receipt '.ci.archive.runs[0].bucket == "ingress-order"'
expect "keeps account ids out of the log" stderr_lacks "111122223333"

run_case wrong-external-id 101 1 "$STS" LUNAR_VAR_S3_BUCKET=ingress-extid \
  LUNAR_VAR_AWS_ASSUME_ROLE_ARNS="$ROLE" LUNAR_VAR_AWS_EXTERNAL_ID=wrong
expect_exit 1
expect "reports STS's refusal" stderr_has "role 1/1 not assumed (AccessDenied)"
expect "says what the role needs" stderr_has "sts:AssumeRole failed for every role"
expect "uploads nothing" no_bucket ingress-extid
expect "writes nothing" nothing_collected

# Control arm: proves the STS stand-in really verifies signatures.
run_case sts-bad-secret 101 1 "$STS" LUNAR_VAR_S3_BUCKET=ingress-badsig \
  LUNAR_VAR_AWS_ASSUME_ROLE_ARNS="$ROLE" LUNAR_VAR_AWS_EXTERNAL_ID="$EXTERNAL_ID" \
  LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=wrong
expect_exit 1
expect "surfaces STS's error code" stderr_has "role 1/1 not assumed (SignatureDoesNotMatch)"
expect "uploads nothing" no_bucket ingress-badsig

# --- Opted in but broken: exit 1, write nothing ---
run_case bad-token 101 1 LUNAR_SECRET_GH_TOKEN=wrong
expect_exit 1
expect "writes nothing on a rejected token" nothing_collected
expect "reports the status" stderr_has "HTTP 401"

# Control arm: proves the S3 stand-in really verifies signatures.
run_case bad-s3-secret 101 1 LUNAR_VAR_S3_BUCKET=badsig LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=wrong
expect_exit 1
expect "writes nothing when S3 rejects the upload" nothing_collected
expect "uploads nothing" no_bucket badsig
expect "surfaces the S3 error code" stderr_has "SignatureDoesNotMatch"

run_case endpoint-no-keys 101 1 LUNAR_SECRET_AWS_ACCESS_KEY_ID= LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=
expect_exit 1
expect "requires static keys for a custom endpoint" stderr_has "s3_endpoint_url is set"

run_case bad-regex 101 1 'LUNAR_VAR_INCLUDE_RUNS_PATTERN=(unclosed'
expect_exit 1
expect "rejects an invalid include_runs_pattern" stderr_has "not a valid regex"

run_case in-progress 104 1
expect_exit 1
expect "refuses an attempt that has not finished" stderr_has "not completed"
expect "writes nothing" nothing_collected

run_case expired 105 1
expect_exit 1
expect "reports logs GitHub no longer has" stderr_has "HTTP 410"
expect "writes nothing" nothing_collected

run_case cap 201 1 LUNAR_VAR_S3_BUCKET=capped LUNAR_VAR_MAX_ARCHIVE_MB=1
expect_exit 1
expect "uploads nothing over the cap" no_bucket capped
expect "says why" stderr_has "max-archive-mb"

# --- API behaviour ---
run_case flaky 301 1
expect_exit 0
expect "retries a 5xx from the run endpoint" receipt '.ci.archive.runs[0].id == 301'

run_case log-lag 401 1
expect_exit 0
expect "waits out a log archive that is not ready yet" receipt '.ci.archive.runs[0].id == 401'

run_case paged-jobs 501 1
expect_exit 0
expect "follows job pagination past 100" receipt '.ci.archive.runs[0].jobs | length == 150'

run_case root-prefix 301 1 LUNAR_VAR_S3_PREFIX=
expect_exit 0
expect "an empty s3_prefix writes at the bucket root" receipt '.ci.archive.runs[0].key == "127.0.0.1_8443/acme/widgets/sha-301/301-1.zip"'

run_case monorepo 301 1 LUNAR_COMPONENT_ID=127.0.0.1:8443/acme/widgets/services/api
expect_exit 0
expect "resolves the repository of a monorepo component" receipt '.ci.archive.runs[0].key | startswith("lunar/ci-archive/127.0.0.1_8443/acme/widgets/sha-301/")'

echo
if [ "$FAILED" -gt 0 ]; then
  echo "$FAILED check(s) failed."
  exit 1
fi
echo "All checks passed."
