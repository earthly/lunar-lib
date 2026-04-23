#!/bin/bash
set -e

# Runs sonar-scanner on the checked-out source, then delegates to the same
# polling + measure-fetch path used by api.sh. If sonar-scanner isn't on PATH,
# downloads the pinned version from GitHub releases into a cache dir and uses
# that. On scanner failure we write .code_quality.native.sonarqube.auto with
# status="scanner-failed" and exit cleanly — no downstream polling.

source "$(dirname "$0")/helpers.sh"

if [ -z "${LUNAR_SECRET_SONARQUBE_TOKEN:-}" ]; then
    echo "sonarqube/auto: SONARQUBE_TOKEN secret not set — skipping." >&2
    exit 0
fi

PROJECT_KEY="$(sq_project_key)"
if [ -z "$PROJECT_KEY" ]; then
    echo "sonarqube/auto: no project key (set sonarqube/project-key meta annotation or project_key input) — skipping." >&2
    exit 0
fi

BASE_URL="$(sq_base_url)"
SCANNER_VERSION="${LUNAR_VAR_AUTO_SCANNER_VERSION:-7.0.0.4796}"
SOURCES="${LUNAR_VAR_AUTO_SOURCES:-.}"
EXTRA_ARGS="${LUNAR_VAR_AUTO_EXTRA_ARGS:-}"

# Resolve or install sonar-scanner.
SCANNER_BIN="$(command -v sonar-scanner || true)"
if [ -z "$SCANNER_BIN" ]; then
    CACHE_DIR="${LUNAR_CACHE_DIR:-/tmp/sonarqube-auto}"
    SCANNER_DIR="${CACHE_DIR}/sonar-scanner-${SCANNER_VERSION}-linux-x64"
    SCANNER_BIN="${SCANNER_DIR}/bin/sonar-scanner"
    if [ ! -x "$SCANNER_BIN" ]; then
        mkdir -p "$CACHE_DIR"
        ZIP="${CACHE_DIR}/sonar-scanner-${SCANNER_VERSION}.zip"
        URL="https://github.com/SonarSource/sonar-scanner-cli/releases/download/${SCANNER_VERSION}/sonar-scanner-cli-${SCANNER_VERSION}-linux-x64.zip"
        if ! curl -fsSL -o "$ZIP" "$URL"; then
            jq -n \
                --arg status "scanner-failed" \
                --arg version "$SCANNER_VERSION" \
                --argjson exit_code 127 \
                --argjson duration 0 \
                '{status: $status, version: $version, exit_code: $exit_code, duration_seconds: $duration, error: "download-failed"}' \
                | lunar collect -j ".code_quality.native.sonarqube.auto" -
            sq_write_source "$PROJECT_KEY" "auto" "scanner-failed"
            exit 0
        fi
        (cd "$CACHE_DIR" && unzip -q -o "$ZIP")
    fi
fi

# Scope args: PR vs default branch.
SCOPE_ARGS=()
if [ -n "${LUNAR_COMPONENT_PR:-}" ]; then
    SCOPE_ARGS+=("-Dsonar.pullrequest.key=${LUNAR_COMPONENT_PR}")
    [ -n "${LUNAR_COMPONENT_HEAD_BRANCH:-}" ] && SCOPE_ARGS+=("-Dsonar.pullrequest.branch=${LUNAR_COMPONENT_HEAD_BRANCH}")
    [ -n "${LUNAR_COMPONENT_BASE_BRANCH:-}" ] && SCOPE_ARGS+=("-Dsonar.pullrequest.base=${LUNAR_COMPONENT_BASE_BRANCH}")
elif [ -n "${LUNAR_COMPONENT_HEAD_BRANCH:-}" ]; then
    SCOPE_ARGS+=("-Dsonar.branch.name=${LUNAR_COMPONENT_HEAD_BRANCH}")
elif [ -n "${LUNAR_COMPONENT_BASE_BRANCH:-}" ]; then
    SCOPE_ARGS+=("-Dsonar.branch.name=${LUNAR_COMPONENT_BASE_BRANCH}")
fi

START_TS=$(date +%s)
set +e
# shellcheck disable=SC2086
"$SCANNER_BIN" \
    "-Dsonar.projectKey=${PROJECT_KEY}" \
    "-Dsonar.host.url=${BASE_URL}" \
    "-Dsonar.token=${LUNAR_SECRET_SONARQUBE_TOKEN}" \
    "-Dsonar.sources=${SOURCES}" \
    "${SCOPE_ARGS[@]}" \
    ${EXTRA_ARGS} >&2
EXIT_CODE=$?
set -e
END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))

# Capture the scanner version from the resolved binary, falling back to input.
RESOLVED_VERSION="$("$SCANNER_BIN" --version 2>/dev/null \
    | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?' \
    | head -1)"
[ -z "$RESOLVED_VERSION" ] && RESOLVED_VERSION="$SCANNER_VERSION"

if [ "$EXIT_CODE" -ne 0 ]; then
    jq -n \
        --arg status "scanner-failed" \
        --arg version "$RESOLVED_VERSION" \
        --argjson exit_code "$EXIT_CODE" \
        --argjson duration "$DURATION" \
        '{status: $status, version: $version, exit_code: $exit_code, duration_seconds: $duration}' \
        | lunar collect -j ".code_quality.native.sonarqube.auto" -
    sq_write_source "$PROJECT_KEY" "auto" "scanner-failed"
    exit 0
fi

jq -n \
    --arg status "complete" \
    --arg version "$RESOLVED_VERSION" \
    --argjson exit_code "$EXIT_CODE" \
    --argjson duration "$DURATION" \
    '{status: $status, version: $version, exit_code: $exit_code, duration_seconds: $duration}' \
    | lunar collect -j ".code_quality.native.sonarqube.auto" -

if ! sq_poll_analysis "$PROJECT_KEY"; then
    sq_write_source "$PROJECT_KEY" "auto" "pending"
    exit 0
fi

sq_collect_measures "$PROJECT_KEY" "auto"
