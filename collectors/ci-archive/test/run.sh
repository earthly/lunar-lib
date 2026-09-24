#!/bin/bash
# Offline end-to-end test for workflow-logs.sh: the real script, curl, jq,
# python3 and lunar CLI against the stand-ins in servers.py. The component is
# GHES-shaped (127.0.0.1:8443/acme/widgets), so the /api/v3 path is exercised
# without any test-only switch in the script.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../workflow-logs.sh"
TMP="$(mktemp -d)"
export S3_DIR="$TMP/s3"
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

# run_case <name> <sha> [VAR=value ...]: runs the collector in a clean env.
run_case() {
  CASE="$1"; local sha="$2"; shift 2
  OUT="$TMP/$CASE.out"; ERR="$TMP/$CASE.err"
  env -i PATH="$PATH" HOME="$TMP" \
    CURL_CA_BUNDLE="$TMP/cert.pem" \
    LUNAR_COLLECT_STDOUT=1 \
    LUNAR_COMPONENT_ID=127.0.0.1:8443/acme/widgets \
    LUNAR_COMPONENT_GIT_SHA="$sha" \
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
nothing_collected() { [ ! -s "$OUT" ]; }
no_bucket() { [ ! -e "$S3_DIR/$1" ]; }
object_path() { echo "$S3_DIR/$(jq -r '.ci.archive.bucket + "/" + .ci.archive.key' "$OUT")"; }
zip_names() { python3 -c 'import sys, zipfile; print("\n".join(sorted(zipfile.ZipFile(sys.argv[1]).namelist())))' "$1"; }

# --- Happy path: archived, expired and in-progress runs in one commit ---
run_case multi sha-multi
expect_exit 0
expect "archives the three completed runs with logs" receipt '.ci.archive.run_count == 3 and ([.ci.archive.runs[].id] | sort) == [101, 102, 103]'
expect "records the expired and in-progress runs as errors" receipt '([.ci.archive.errors[] | .run_id] | sort) == [104, 105]'
expect "explains the 410" receipt '.ci.archive.errors[] | select(.run_id == 105) | .reason | test("expired")'
expect "writes uri, key and size" receipt '(.ci.archive.uri | startswith("s3://archive/lunar/ci-archive/127.0.0.1_8443/acme/widgets/sha-multi/")) and .ci.archive.size_bytes > 0'
expect "records log sizes per run" receipt 'all(.ci.archive.runs[]; .log_bytes > 0)'
expect "stamps the source block" receipt '.ci.archive.source | .tool == "ci-archive" and .integration == "after-json" and .collected_sha == "sha-multi"'
OBJ="$(object_path)"
expect "uploads the object to S3" test -s "$OBJ"
expect "object holds manifest.json and one logs.zip per archived run" \
  test "$(zip_names "$OBJ" | tr '\n' ' ')" = "manifest.json runs/101/logs.zip runs/102/logs.zip runs/103/logs.zip "
expect "manifest.json matches the receipt" python3 -c '
import json, sys, zipfile
m = json.loads(zipfile.ZipFile(sys.argv[1]).read("manifest.json"))
r = json.load(open(sys.argv[2]))["ci"]["archive"]
assert m["sha"] == "sha-multi" and m["repository"] == "acme/widgets"
assert m["runs"] == r["runs"] and m["errors"] == r["errors"]
' "$OBJ" "$OUT"

# --- Nothing to archive / not configured: exit 0, write nothing ---
run_case no-runs sha-none
expect_exit 0
expect "writes nothing when the commit has no runs" nothing_collected
expect "says why" stderr_has "no completed workflow runs"

run_case no-bucket sha-multi LUNAR_VAR_S3_BUCKET=
expect_exit 0
expect "writes nothing without s3_bucket" nothing_collected
expect "says why" stderr_has "s3_bucket input is not set"

run_case no-token sha-multi LUNAR_SECRET_GH_TOKEN=
expect_exit 0
expect "writes nothing without GH_TOKEN" nothing_collected
expect "says why" stderr_has "GH_TOKEN secret is not set"

# --- Opted in but broken: exit 1, write nothing ---
run_case bad-token sha-multi LUNAR_SECRET_GH_TOKEN=wrong
expect_exit 1
expect "writes nothing on a rejected token" nothing_collected
expect "says the token was rejected" stderr_has "GH_TOKEN was rejected"

# Control arm: proves the S3 stand-in really verifies signatures.
run_case bad-s3-secret sha-multi LUNAR_VAR_S3_BUCKET=badsig LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=wrong
expect_exit 1
expect "writes nothing when S3 rejects the upload" nothing_collected
expect "uploads nothing" no_bucket badsig
expect "surfaces the S3 error code" stderr_has "SignatureDoesNotMatch"

run_case endpoint-no-keys sha-multi LUNAR_SECRET_AWS_ACCESS_KEY_ID= LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=
expect_exit 1
expect "requires static keys for a custom endpoint" stderr_has "s3_endpoint_url is set"

run_case bad-regex sha-multi 'LUNAR_VAR_INCLUDE_RUNS_PATTERN=(unclosed'
expect_exit 1
expect "rejects an invalid include_runs_pattern" stderr_has "not a valid regex"

# --- Size cap: record the reason, upload nothing ---
run_case cap sha-big LUNAR_VAR_S3_BUCKET=capped LUNAR_VAR_MAX_ARCHIVE_MB=1
expect_exit 0
expect "uploads nothing over the cap" no_bucket capped
expect "records the cap as the reason" receipt '(.ci.archive | has("uri") | not) and (.ci.archive.errors[] | .reason | test("max_archive_mb"))'
expect "does not describe runs that were never uploaded" receipt '.ci.archive | has("runs") | not'

# --- Inputs and API behaviour ---
run_case filter sha-multi 'LUNAR_VAR_INCLUDE_RUNS_PATTERN=^(build|deploy)$'
expect_exit 0
expect "archives only runs matching include_runs_pattern" receipt '[.ci.archive.runs[].id] == [101]'
expect "still reports a matching in-progress run" receipt '[.ci.archive.errors[].run_id] == [104]'

run_case paged sha-paged
expect_exit 0
expect "follows pagination past 100 runs" receipt '.ci.archive.run_count == 105'

run_case flaky sha-flaky
expect_exit 0
expect "retries a 5xx from the runs listing" receipt '.ci.archive.run_count == 1'

run_case root-prefix sha-flaky LUNAR_VAR_S3_PREFIX=
expect_exit 0
expect "an empty s3_prefix writes at the bucket root" receipt '.ci.archive.key | startswith("127.0.0.1_8443/acme/widgets/sha-flaky/")'

echo
if [ "$FAILED" -gt 0 ]; then
  echo "$FAILED check(s) failed."
  exit 1
fi
echo "All checks passed."
