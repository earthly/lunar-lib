#!/bin/bash
set -eo pipefail

# Archive the CI workflow run attempt this collector fired for -- run metadata,
# jobs and the full log archive -- to S3, and record it as one entry under
# .ci.archive.runs.
#
# Runs on the after-ci-pipeline hook: once per finished run attempt, re-runs
# included, with the run in LUNAR_CI_PIPELINE_*. The archiving is archive-run.sh,
# shared with the GitHub Action; this wrapper supplies what the Hub knows in
# place of a CI job: the repository, from the component, and AWS credentials,
# from the pod's IAM role or the collector secrets, optionally exchanged for a
# role in the bucket's account.

log() { echo "ci-archive: $*" >&2; }

S3_BUCKET="${LUNAR_VAR_S3_BUCKET:-}"
S3_ENDPOINT_URL="${LUNAR_VAR_S3_ENDPOINT_URL:-}"
INCLUDE_RUNS_PATTERN="${LUNAR_VAR_INCLUDE_RUNS_PATTERN:-}"
RUN_ID="${LUNAR_CI_PIPELINE_RUN_ID:-}"
ATTEMPT="${LUNAR_CI_PIPELINE_RUN_ATTEMPT:-}"
WORKFLOW="${LUNAR_CI_PIPELINE_NAME:-}"

if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  log "GH_TOKEN secret is not set; skipping."
  exit 0
fi
if [ -z "$RUN_ID" ] || [ -z "$ATTEMPT" ] || [ -z "${LUNAR_COMPONENT_ID:-}" ]; then
  log "no workflow run in context: this collector runs on the Hub's after-ci-pipeline hook. Skipping."
  exit 0
fi
if [ -n "$INCLUDE_RUNS_PATTERN" ]; then
  if ! jq -n --arg re "$INCLUDE_RUNS_PATTERN" '"" | test($re)' >/dev/null 2>&1; then
    log "ERROR: include_runs_pattern is not a valid regex: ${INCLUDE_RUNS_PATTERN}"
    exit 1
  fi
  if ! jq -en --arg re "$INCLUDE_RUNS_PATTERN" --arg name "$WORKFLOW" '$name | test($re)' >/dev/null; then
    log "workflow '${WORKFLOW}' does not match include_runs_pattern; skipping run ${RUN_ID}."
    exit 0
  fi
fi

# Component IDs are <host>/<owner>/<repository>[/<subpath>...]; monorepo
# components append a path after the repository.
HOST="${LUNAR_COMPONENT_ID%%/*}"
REST="${LUNAR_COMPONENT_ID#*/}"
OWNER="${REST%%/*}"
REST="${REST#*/}"
REPO="${OWNER}/${REST%%/*}"
case "$HOST" in
  *gitlab*) log "GitHub Actions only; ${HOST} is not supported. Skipping."; exit 0 ;;
esac
API_BASE="https://api.github.com"
if [ "$HOST" != "github.com" ]; then
  API_BASE="https://${HOST}/api/v3"
fi

# --- AWS credentials ---
# shellcheck source=/dev/null
source "$(dirname "$0")/aws-credentials.sh"

UPLOAD=true
if [ -z "$S3_BUCKET" ]; then
  UPLOAD=false
  log "s3_bucket is not set: recording run ${RUN_ID} attempt ${ATTEMPT} without uploading it."
else
  s3_region || exit 1
  # Named per run attempt, so the bucket account's CloudTrail says which run
  # each upload belongs to.
  s3_credentials "lunar-ci-archive-${RUN_ID}-${ATTEMPT}" || exit 1
  log "uploading to bucket ${S3_BUCKET} (${REGION}) with AWS credentials from ${CRED_SOURCE}."
fi

GH_TOKEN="$LUNAR_SECRET_GH_TOKEN" \
GITHUB_SERVER_URL="https://${HOST}" GITHUB_API_URL="$API_BASE" \
CI_ARCHIVE_REPOSITORY="$REPO" CI_ARCHIVE_RUN_ID="$RUN_ID" CI_ARCHIVE_RUN_ATTEMPT="$ATTEMPT" \
CI_ARCHIVE_UPLOAD="$UPLOAD" CI_ARCHIVE_SHA="${LUNAR_COMPONENT_GIT_SHA:-}" CI_ARCHIVE_TRIGGERED_BY_RUN_ID="${LUNAR_CI_PIPELINE_TRIGGERED_BY_RUN_ID:-}" \
CI_ARCHIVE_ORIGIN_SOURCE="${LUNAR_CI_PIPELINE_ORIGIN_SOURCE:-}" \
CI_ARCHIVE_S3_BUCKET="$S3_BUCKET" CI_ARCHIVE_S3_PREFIX="${LUNAR_VAR_S3_PREFIX-lunar/ci-archive}" \
CI_ARCHIVE_S3_ENDPOINT_URL="$S3_ENDPOINT_URL" CI_ARCHIVE_AWS_REGION="$REGION" \
CI_ARCHIVE_MAX_ARCHIVE_MB="${LUNAR_VAR_MAX_ARCHIVE_MB:-512}" CI_ARCHIVE_INTEGRATION=after-ci-pipeline \
CI_ARCHIVE_INCLUDE_EVENTS="${LUNAR_VAR_INCLUDE_EVENTS:-}" \
AWS_ACCESS_KEY_ID="$AWS_SIGV4_KEY" AWS_SECRET_ACCESS_KEY="$AWS_SIGV4_SECRET" AWS_SESSION_TOKEN="$AWS_SIGV4_TOKEN" \
  exec bash "$(dirname "$0")/archive-run.sh"
