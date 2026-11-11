#!/bin/bash

# Shared helpers for the sonarqube collector — API auth, project key resolution,
# polling, and Component JSON writes. Sourced from api.sh, auto.sh, and
# github-app.sh. config.sh and cicd.sh do not need this.

# Resolve the SonarQube/SonarCloud base URL.
sq_base_url() {
    local url="${LUNAR_VAR_SONARQUBE_BASE_URL:-https://sonarcloud.io}"
    echo "${url%/}"
}

# Resolve the project key: cataloger-set meta annotation first, then explicit input.
# Echoes the key to stdout, or nothing if unresolved.
sq_project_key() {
    local key=""
    if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
        key="$(echo "$LUNAR_COMPONENT_META" | jq -r '."sonarqube/project-key" // empty')"
    fi
    if [ -z "$key" ] && [ -n "${LUNAR_VAR_PROJECT_KEY:-}" ]; then
        key="$LUNAR_VAR_PROJECT_KEY"
    fi
    echo "$key"
}

# Authenticated GET against the SonarQube Web API. Uses token-as-basic-user
# (empty password) per the documented convention. Echoes body on success,
# non-zero exit on failure.
sq_api_get() {
    local path="$1"
    local base
    base="$(sq_base_url)"
    curl -fsS -u "${LUNAR_SECRET_SONARQUBE_TOKEN}:" "${base}${path}" # gitleaks:allow
}

# Convert SonarQube numeric rating ("1.0".."5.0") to letter (A..E).
# Echoes "A".."E", or empty string if the value is unparseable.
sq_rating_to_letter() {
    local raw="$1"
    case "${raw%%.*}" in
        1) echo "A" ;;
        2) echo "B" ;;
        3) echo "C" ;;
        4) echo "D" ;;
        5) echo "E" ;;
        *) echo "" ;;
    esac
}

# Emit the SonarQube Web API scope query-param suffix for the current context.
# On PRs: "&pullRequest=<n>". On default branch: "&branch=<branch>" (empty if the
# branch isn't known — SonarQube will fall back to the project's default).
sq_scope_query() {
    if [ -n "${LUNAR_COMPONENT_PR:-}" ]; then
        echo "&pullRequest=${LUNAR_COMPONENT_PR}"
    elif [ -n "${LUNAR_COMPONENT_HEAD_BRANCH:-}" ]; then
        echo "&branch=${LUNAR_COMPONENT_HEAD_BRANCH}"
    elif [ -n "${LUNAR_COMPONENT_BASE_BRANCH:-}" ]; then
        echo "&branch=${LUNAR_COMPONENT_BASE_BRANCH}"
    else
        echo ""
    fi
}

# Poll until SonarQube has published the analysis of LUNAR_COMPONENT_GIT_SHA, or
# until api_poll_timeout_seconds elapses: api/project_analyses/search on branch
# commits, sq_poll_pr_analysis on PR commits. Returns 0 on match, 1 on timeout or
# error. Silent on success; logs on timeout.
sq_poll_analysis() {
    local project_key="$1"
    if [ -n "${LUNAR_COMPONENT_PR:-}" ]; then
        sq_poll_pr_analysis "$project_key"
        return
    fi
    local timeout="${LUNAR_VAR_API_POLL_TIMEOUT_SECONDS:-180}"
    local interval="${LUNAR_VAR_API_POLL_INTERVAL_SECONDS:-10}"
    local scope
    scope="$(sq_scope_query)"
    local expected="${LUNAR_COMPONENT_GIT_SHA:-}"
    local elapsed=0

    if [ -z "$expected" ]; then
        # No SHA to match against — single-shot query.
        sq_api_get "/api/project_analyses/search?project=${project_key}${scope}&ps=1" >/dev/null 2>&1 && return 0
        return 1
    fi

    while [ "$elapsed" -lt "$timeout" ]; do
        local resp revision
        resp="$(sq_api_get "/api/project_analyses/search?project=${project_key}${scope}&ps=1" 2>/dev/null || echo '{"analyses":[]}')"
        revision="$(echo "$resp" | jq -r '.analyses[0].revision // empty')"
        if [ -n "$revision" ] && [ "$revision" = "$expected" ]; then
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    echo "sonarqube: analysis for ${expected} did not appear within ${timeout}s — writing analysis_status=pending" >&2
    return 1
}

# api/project_analyses/search has no pullRequest param (Server or Cloud) and
# answers for the main branch, so PR commits wait on the PR's own entry in
# api/project_pull_requests/list. SonarCloud reports the analyzed commit there;
# SonarQube Server reports none, so the analysis must not predate the commit.
sq_poll_pr_analysis() {
    local project_key="$1"
    local timeout="${LUNAR_VAR_API_POLL_TIMEOUT_SECONDS:-180}"
    local interval="${LUNAR_VAR_API_POLL_INTERVAL_SECONDS:-10}"
    local pr="$LUNAR_COMPONENT_PR"
    local expected="${LUNAR_COMPONENT_GIT_SHA:-}"
    local path="/api/project_pull_requests/list?project=${project_key}"
    local elapsed=0 not_before resp state="no response"

    if [ -z "$expected" ]; then
        # No SHA to match against — single-shot check that the PR was analyzed.
        sq_api_get "$path" 2>/dev/null | jq -e --arg pr "$pr" 'any(.pullRequests[]?; .key == $pr)' >/dev/null 2>&1
        return
    fi

    # The head commit's committer time; without a checkout, when this run started.
    not_before="$(git log -1 --format=%ct "$expected" 2>/dev/null || true)"
    case "$not_before" in ''|*[!0-9]*) not_before="$(date +%s)" ;; esac

    while [ "$elapsed" -lt "$timeout" ]; do
        if resp="$(sq_api_get "$path" 2>/dev/null)"; then
            state="$(printf '%s' "$resp" | jq -r --arg pr "$pr" --arg sha "$expected" --argjson not_before "$not_before" '
              def epoch: (.[0:19] + "Z" | fromdateiso8601) as $t
                | (.[19:] | sub("^\\.[0-9]+"; "") | gsub(":"; "")) as $z
                | if ($z | test("^[+-][0-9]{4}$"))
                  then $t - (($z[1:3] | tonumber) * 3600 + ($z[3:5] | tonumber) * 60) * (if $z[0:1] == "-" then -1 else 1 end)
                  else $t end;
              (first(.pullRequests[]? | select(.key == $pr)) // null) as $e
              | if $e == null or ($e.analysisDate // "") == "" then "pull request not analyzed yet"
                elif ($e.commit.sha // "") != "" then
                  if $e.commit.sha == $sha then "match" else "latest analysis is of \($e.commit.sha)" end
                elif ($e.analysisDate | epoch) >= $not_before then "match"
                else "latest analysis (\($e.analysisDate)) predates \($not_before | todate)" end
            ' 2>/dev/null)" || state="unreadable response"
        else
            state="API request failed"
        fi
        [ "$state" = "match" ] && return 0
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    echo "sonarqube: pull request ${pr} analysis for ${expected} did not appear within ${timeout}s (${state}) — writing analysis_status=pending" >&2
    return 1
}

# Fetch and map SonarQube measures for the current scope.
# Writes the full tool-agnostic + native payload to Component JSON.
# Args: $1 = project_key, $2 = integration ("api"|"auto").
sq_collect_measures() {
    local project_key="$1"
    local integration="$2"
    local scope
    scope="$(sq_scope_query)"

    local metric_keys
    metric_keys="alert_status,coverage,duplicated_lines_density,bugs,vulnerabilities,code_smells,security_hotspots,ncloc,reliability_rating,security_rating,sqale_rating,security_review_rating,sqale_index"

    local measures_json
    measures_json="$(sq_api_get "/api/measures/component?component=${project_key}&metricKeys=${metric_keys}${scope}" 2>/dev/null || echo '{}')"

    if [ -z "$measures_json" ] || [ "$(echo "$measures_json" | jq -r '.component.measures // empty')" = "" ]; then
        echo "sonarqube: no measures returned for ${project_key} — writing analysis_status=pending" >&2
        sq_write_source "$project_key" "$integration" "pending"
        return 0
    fi

    # Extract each measure by key (SonarCloud returns measures as an array).
    local m
    m="$(echo "$measures_json" | jq -c '.component.measures | map({(.metric): (.value // .periods[0].value // null)}) | add // {}')"

    local alert coverage dup bugs vulns smells hotspots ncloc rel sec maint secrev debt
    alert="$(echo "$m" | jq -r '.alert_status // empty')"
    coverage="$(echo "$m" | jq -r '.coverage // empty')"
    dup="$(echo "$m" | jq -r '.duplicated_lines_density // empty')"
    bugs="$(echo "$m" | jq -r '.bugs // "0"')"
    vulns="$(echo "$m" | jq -r '.vulnerabilities // "0"')"
    smells="$(echo "$m" | jq -r '.code_smells // "0"')"
    hotspots="$(echo "$m" | jq -r '.security_hotspots // "0"')"
    ncloc="$(echo "$m" | jq -r '.ncloc // "0"')"
    rel="$(sq_rating_to_letter "$(echo "$m" | jq -r '.reliability_rating // empty')")"
    sec="$(sq_rating_to_letter "$(echo "$m" | jq -r '.security_rating // empty')")"
    maint="$(sq_rating_to_letter "$(echo "$m" | jq -r '.sqale_rating // empty')")"
    secrev="$(sq_rating_to_letter "$(echo "$m" | jq -r '.security_review_rating // empty')")"
    debt="$(echo "$m" | jq -r '.sqale_index // "0"')"

    # Quality gate detail (status + failed condition count). Fall back to
    # alert_status if the structured endpoint is unavailable.
    local gate_json gate_status gate_failed
    gate_json="$(sq_api_get "/api/qualitygates/project_status?projectKey=${project_key}${scope}" 2>/dev/null || echo '{}')"
    gate_status="$(echo "$gate_json" | jq -r '.projectStatus.status // empty')"
    gate_failed="$(echo "$gate_json" | jq -r '[.projectStatus.conditions[]? | select(.status == "ERROR")] | length')"
    if [ -z "$gate_status" ]; then
        gate_status="$alert"
    fi
    if [ -z "$gate_failed" ] || [ "$gate_failed" = "null" ]; then
        gate_failed=0
    fi

    # Severity-bucketed issue counts via the issues/search facets endpoint.
    local issues_json issues_out
    issues_json="$(sq_api_get "/api/issues/search?componentKeys=${project_key}&facets=severities&ps=1${scope}" 2>/dev/null || echo '{}')"
    issues_out="$(echo "$issues_json" | jq -c '
      (.facets // [] | map(select(.property=="severities"))[0].values // []) as $f
      | (reduce $f[] as $v ({}; .[$v.val] = $v.count)) as $by
      | {
          total: (.total // 0),
          critical: (($by.BLOCKER // 0) + ($by.CRITICAL // 0)),
          high: ($by.MAJOR // 0),
          medium: ($by.MINOR // 0),
          low: ($by.INFO // 0)
        }
    ' 2>/dev/null || echo '{"total":0,"critical":0,"high":0,"medium":0,"low":0}')"

    # Tool-agnostic fields.
    local passing="false"
    [ "$gate_status" = "OK" ] && passing="true"

    sq_write_source "$project_key" "$integration" "complete"
    lunar collect -j ".code_quality.passing" "$passing"

    if [ -n "$coverage" ]; then
        lunar collect -j ".code_quality.coverage_percentage" "$coverage"
    fi
    if [ -n "$dup" ]; then
        lunar collect -j ".code_quality.duplication_percentage" "$dup"
    fi

    echo "$issues_out" | lunar collect -j ".code_quality.issues" -

    # Native SonarQube block.
    jq -n \
        --arg status "${gate_status:-UNKNOWN}" \
        --argjson failed "${gate_failed:-0}" \
        '{status: $status, conditions_failed: $failed}' \
        | lunar collect -j ".code_quality.native.sonarqube.quality_gate" -

    jq -n \
        --arg rel "$rel" \
        --arg sec "$sec" \
        --arg maint "$maint" \
        --arg secrev "$secrev" \
        '{reliability: $rel, security: $sec, maintainability: $maint, security_review: $secrev} | with_entries(select(.value != ""))' \
        | lunar collect -j ".code_quality.native.sonarqube.ratings" -

    jq -n \
        --argjson bugs "${bugs:-0}" \
        --argjson vulns "${vulns:-0}" \
        --argjson smells "${smells:-0}" \
        --argjson hotspots "${hotspots:-0}" \
        --argjson ncloc "${ncloc:-0}" \
        --argjson debt "${debt:-0}" \
        '{bugs: $bugs, vulnerabilities: $vulns, code_smells: $smells, security_hotspots: $hotspots, lines_of_code: $ncloc, technical_debt_minutes: $debt}' \
        | lunar collect -j ".code_quality.native.sonarqube.metrics" -
}

# Write the .code_quality.source metadata block.
# Args: $1 = project_key, $2 = integration, $3 = analysis_status.
sq_write_source() {
    local project_key="$1"
    local integration="$2"
    local analysis_status="$3"
    local base
    base="$(sq_base_url)"
    jq -n \
        --arg tool "sonarqube" \
        --arg integration "$integration" \
        --arg key "$project_key" \
        --arg url "$base" \
        --arg status "$analysis_status" \
        '{tool: $tool, integration: $integration, project_key: $key, api_url: $url, analysis_status: $status}' \
        | lunar collect -j ".code_quality.source" -
}
