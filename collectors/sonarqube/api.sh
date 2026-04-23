#!/bin/bash
set -e

# Queries SonarQube/SonarCloud Web API for code-quality metrics on the current
# commit. Scopes with branch=<default> on default-branch commits and
# pullRequest=<n> on PR commits. Polls api/project_analyses/search until the
# analysis for LUNAR_COMPONENT_GIT_SHA appears or api_poll_timeout_seconds
# elapses, then fetches measures + quality-gate status + issue severity facet
# and writes both tool-agnostic (.code_quality.*) and native
# (.code_quality.native.sonarqube.*) fields.

source "$(dirname "$0")/helpers.sh"

if [ -z "${LUNAR_SECRET_SONARQUBE_TOKEN:-}" ]; then
    echo "sonarqube/api: SONARQUBE_TOKEN secret not set — skipping." >&2
    exit 0
fi

PROJECT_KEY="$(sq_project_key)"
if [ -z "$PROJECT_KEY" ]; then
    echo "sonarqube/api: no project key (set sonarqube/project-key meta annotation or project_key input) — skipping." >&2
    exit 0
fi

if ! sq_poll_analysis "$PROJECT_KEY"; then
    sq_write_source "$PROJECT_KEY" "api" "pending"
    exit 0
fi

sq_collect_measures "$PROJECT_KEY" "api"
