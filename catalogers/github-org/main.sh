#!/bin/bash
set -e

# GitHub Organization Cataloger
# Syncs all repositories from a GitHub organization as Lunar components

# GitHub host: "github.com" (default) or a GitHub Enterprise Server hostname.
# Accept a full URL too and normalize down to the bare host (strip scheme + any
# trailing path), so "github.acme.com", "https://github.acme.com" and
# "https://github.acme.com/" all resolve to the same hostname.
GITHUB_HOST_RAW="${LUNAR_VAR_GITHUB_HOST:-github.com}"
GITHUB_HOST=$(echo "$GITHUB_HOST_RAW" | sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://##; s#/.*$##')
GITHUB_HOST="${GITHUB_HOST:-github.com}"
export GH_HOST="$GITHUB_HOST"

# Authenticate the gh CLI. github.com and a GitHub Enterprise Server are separate
# hosts with separate credentials, so read separate secrets and route each to the
# variable gh selects by host:
#   - github.com        -> GH_TOKEN            from LUNAR_SECRET_GH_TOKEN
#   - GitHub Enterprise -> GH_ENTERPRISE_TOKEN from LUNAR_SECRET_GH_ENTERPRISE_TOKEN,
#                          falling back to LUNAR_SECRET_GH_TOKEN so single-token
#                          setups that only ever set GH_TOKEN keep working.
# A matching token already exported in the environment is honored as a last resort.
if [ "$GITHUB_HOST" = "github.com" ]; then
    GH_AUTH_TOKEN="${LUNAR_SECRET_GH_TOKEN:-${GH_TOKEN:-}}"
    if [ -z "$GH_AUTH_TOKEN" ]; then
        echo "Error: LUNAR_SECRET_GH_TOKEN (or GH_TOKEN) must be set for github.com" >&2
        exit 1
    fi
    export GH_TOKEN="$GH_AUTH_TOKEN"
else
    GH_AUTH_TOKEN="${LUNAR_SECRET_GH_ENTERPRISE_TOKEN:-${LUNAR_SECRET_GH_TOKEN:-${GH_ENTERPRISE_TOKEN:-${GH_TOKEN:-}}}}"
    if [ -z "$GH_AUTH_TOKEN" ]; then
        echo "Error: LUNAR_SECRET_GH_ENTERPRISE_TOKEN (or LUNAR_SECRET_GH_TOKEN) must be set for GitHub Enterprise host $GITHUB_HOST" >&2
        exit 1
    fi
    export GH_ENTERPRISE_TOKEN="$GH_AUTH_TOKEN"
fi

# Required input
ORG_NAME="${LUNAR_VAR_ORG_NAME:?org_name input is required}"

# Optional inputs with defaults
INCLUDE_PUBLIC="${LUNAR_VAR_INCLUDE_PUBLIC:-true}"
INCLUDE_PRIVATE="${LUNAR_VAR_INCLUDE_PRIVATE:-true}"
INCLUDE_INTERNAL="${LUNAR_VAR_INCLUDE_INTERNAL:-true}"
INCLUDE_ARCHIVED="${LUNAR_VAR_INCLUDE_ARCHIVED:-false}"
INCLUDE_REPOS="${LUNAR_VAR_INCLUDE_REPOS:-}"
EXCLUDE_REPOS="${LUNAR_VAR_EXCLUDE_REPOS:-}"
TAG_PREFIX="${LUNAR_VAR_TAG_PREFIX:-gh-}"
DEFAULT_OWNER="${LUNAR_VAR_DEFAULT_OWNER:-}"
DEFAULT_DOMAIN="${LUNAR_VAR_DEFAULT_DOMAIN:-}"

# Rate limit / retry settings
MAX_RETRIES=5
INITIAL_BACKOFF=5  # seconds

# Build list of visibilities to fetch
VISIBILITIES=()
if [ "$INCLUDE_PUBLIC" = "true" ]; then
    VISIBILITIES+=("public")
fi
if [ "$INCLUDE_PRIVATE" = "true" ]; then
    VISIBILITIES+=("private")
fi
if [ "$INCLUDE_INTERNAL" = "true" ]; then
    VISIBILITIES+=("internal")
fi

if [ ${#VISIBILITIES[@]} -eq 0 ]; then
    echo "Error: At least one visibility type must be enabled"
    exit 1
fi

echo "Cataloging repos from GitHub org: $ORG_NAME"
echo "GitHub host: $GITHUB_HOST"
echo "Visibilities: ${VISIBILITIES[*]}"
echo "Include archived: $INCLUDE_ARCHIVED"
[ -n "$INCLUDE_REPOS" ] && echo "Include patterns: $INCLUDE_REPOS"
[ -n "$EXCLUDE_REPOS" ] && echo "Exclude patterns: $EXCLUDE_REPOS"
[ -n "$DEFAULT_OWNER" ] && echo "Default owner: $DEFAULT_OWNER"
[ -n "$DEFAULT_DOMAIN" ] && echo "Default domain: $DEFAULT_DOMAIN"

# Convert glob pattern to regex
# Escapes regex special chars, converts * to .* and ? to .
glob_to_regex() {
    local glob="$1"
    # Escape regex special chars (except * and ?)
    local escaped
    escaped=$(echo "$glob" | sed -E 's/([.+^${}()|\\])/\\\1/g')
    # Convert glob wildcards to regex
    escaped=$(echo "$escaped" | sed 's/\*/.\*/g; s/\?/./g')
    echo "^${escaped}$"
}

# Convert comma-separated glob patterns to jq-compatible regex alternation
# e.g., "api-*,backend-*" -> "^api-.*$|^backend-.*$"
patterns_to_regex() {
    local patterns="$1"
    if [ -z "$patterns" ]; then
        echo ""
        return
    fi
    
    local regex_parts=()
    IFS=',' read -ra PATTERN_ARRAY <<< "$patterns"
    for pattern in "${PATTERN_ARRAY[@]}"; do
        # Trim whitespace
        pattern=$(echo "$pattern" | xargs)
        if [ -n "$pattern" ]; then
            regex_parts+=("$(glob_to_regex "$pattern")")
        fi
    done
    
    # Join with |
    local IFS='|'
    echo "${regex_parts[*]}"
}

# Fetch repos with retry and exponential backoff
fetch_repos_with_retry() {
    local visibility="$1"
    local attempt=1
    local backoff=$INITIAL_BACKOFF
    
    while [ $attempt -le $MAX_RETRIES ]; do
        # Build gh command
        local GH_ARGS=(repo list "$ORG_NAME" --visibility "$visibility" --limit 10000)
        GH_ARGS+=(--json "name,url,description,repositoryTopics,isArchived,visibility")
        
        if [ "$INCLUDE_ARCHIVED" = "false" ]; then
            GH_ARGS+=(--no-archived)
        fi
        
        # Try to fetch
        local output
        local exit_code=0
        output=$(gh "${GH_ARGS[@]}" 2>&1) || exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo "$output"
            return 0
        fi
        
        # Check for rate limit error
        if echo "$output" | grep -qi "rate limit\|secondary rate\|abuse detection"; then
            echo "Rate limited (attempt $attempt/$MAX_RETRIES), waiting ${backoff}s..." >&2
            sleep $backoff
            backoff=$((backoff * 2))
            attempt=$((attempt + 1))
            continue
        fi
        
        # Check for other retryable errors (network issues, 5xx)
        if echo "$output" | grep -qiE "timeout|connection|503|502|500"; then
            echo "Transient error (attempt $attempt/$MAX_RETRIES), waiting ${backoff}s..." >&2
            sleep $backoff
            backoff=$((backoff * 2))
            attempt=$((attempt + 1))
            continue
        fi
        
        # Non-retryable error
        echo "Error fetching $visibility repos: $output" >&2
        return 1
    done
    
    echo "Failed to fetch $visibility repos after $MAX_RETRIES attempts" >&2
    return 1
}

# Convert patterns to regex for jq
INCLUDE_REGEX=$(patterns_to_regex "$INCLUDE_REPOS")
EXCLUDE_REGEX=$(patterns_to_regex "$EXCLUDE_REPOS")

[ -n "$INCLUDE_REGEX" ] && echo "Include regex: $INCLUDE_REGEX"
[ -n "$EXCLUDE_REGEX" ] && echo "Exclude regex: $EXCLUDE_REGEX"

# Use temp file for large dataset handling
TEMP_FILE=$(mktemp)
trap 'rm -f "$TEMP_FILE" "${TEMP_FILE}.chunk" "${TEMP_FILE}.new"' EXIT

# Initialize with empty array
echo "[]" > "$TEMP_FILE"

# Collect repos from all visibility levels
for visibility in "${VISIBILITIES[@]}"; do
    echo "Fetching $visibility repos..."
    
    if ! REPOS=$(fetch_repos_with_retry "$visibility"); then
        echo "Failed to fetch $visibility repos, aborting"
        exit 1
    fi
    
    REPO_COUNT=$(echo "$REPOS" | jq 'length')
    echo "Found $REPO_COUNT $visibility repos"
    
    # Merge into temp file (single jq call, not accumulating in memory)
    echo "$REPOS" > "${TEMP_FILE}.chunk"
    jq -s 'add' "$TEMP_FILE" "${TEMP_FILE}.chunk" > "${TEMP_FILE}.new"
    mv "${TEMP_FILE}.new" "$TEMP_FILE"
    rm -f "${TEMP_FILE}.chunk"
done

TOTAL_COUNT=$(jq 'length' "$TEMP_FILE")
echo "Total repos fetched: $TOTAL_COUNT"

# Batch size for lunar catalog calls
BATCH_SIZE=1000

# Filter and transform all repos in a single jq call
# Output as array of {key, value} pairs for easier batching
CATALOG_ENTRIES=$(jq \
    --arg prefix "$TAG_PREFIX" \
    --arg owner "$DEFAULT_OWNER" \
    --arg domain "$DEFAULT_DOMAIN" \
    --arg include_regex "$INCLUDE_REGEX" \
    --arg exclude_regex "$EXCLUDE_REGEX" \
    '
    # Filter repos based on include/exclude patterns
    [.[] | 
        # Apply include filter (if specified, must match)
        select(
            ($include_regex == "") or 
            (.name | test($include_regex))
        ) |
        # Apply exclude filter (if specified, must not match)
        select(
            ($exclude_regex == "") or 
            (.name | test($exclude_regex) | not)
        )
    ] |
    
    # Transform to catalog format as array of entries (for batching)
    [.[] | {
        key: (.url | gsub("https://"; "")),
        value: (
            {
                tags: ([(.repositoryTopics // [])[] | .name | "\($prefix)\(.)"] + ["github-visibility-\(.visibility | ascii_downcase)"]),
                meta: {
                    description: .description,
                    visibility: .visibility,
                    archived: (if .isArchived then "true" else "false" end),
                }
            } + (if $owner != "" then {owner: $owner} else {} end)
              + (if $domain != "" then {domain: $domain} else {} end)
        )
    }]
    ' "$TEMP_FILE")

# Get total count
TOTAL_ENTRIES=$(echo "$CATALOG_ENTRIES" | jq 'length')
echo "Components after filtering: $TOTAL_ENTRIES"

if [ "$TOTAL_ENTRIES" -eq 0 ]; then
    echo "No components to catalog"
    exit 0
fi

# Register the default domain BEFORE writing components. Every component above
# carries `domain: $DEFAULT_DOMAIN`, and the hub's validateDomainRefs drops the
# entire catalog merge if a component references a domain absent from .domains.
# Writing it first keeps every intermediate merge-save valid. A higher-precedence
# definition in lunar-config.yml (or a later cataloger) still wins on merge, so
# this is just the safety net that keeps the reference valid.
if [ -n "$DEFAULT_DOMAIN" ]; then
    echo "Registering domain '$DEFAULT_DOMAIN' under .domains"
    if jq -n --arg d "$DEFAULT_DOMAIN" \
        '{($d): {description: "Created by the github-org cataloger"}}' \
        | lunar catalog raw --json '.domains' -; then
        echo "Registered domain '$DEFAULT_DOMAIN'"
    else
        echo "Failed to register domain '$DEFAULT_DOMAIN'" >&2
        exit 1
    fi
fi

# Process in batches
BATCH_NUM=0
SUCCESS_COUNT=0
FAIL_COUNT=0

while true; do
    START=$((BATCH_NUM * BATCH_SIZE))
    
    # Check if we've processed all entries
    if [ "$START" -ge "$TOTAL_ENTRIES" ]; then
        break
    fi
    
    END=$((START + BATCH_SIZE))
    if [ "$END" -gt "$TOTAL_ENTRIES" ]; then
        END=$TOTAL_ENTRIES
    fi
    
    BATCH_NUM=$((BATCH_NUM + 1))
    BATCH_COUNT=$((END - START))
    
    echo "Processing batch $BATCH_NUM: components $((START + 1))-$END of $TOTAL_ENTRIES"
    
    # Extract batch and convert to object format for lunar catalog
    BATCH_COMPONENTS=$(echo "$CATALOG_ENTRIES" | jq \
        --argjson start "$START" \
        --argjson count "$BATCH_COUNT" \
        '.[$start:$start + $count] | from_entries')
    
    # Write batch to catalog
    if echo "$BATCH_COMPONENTS" | lunar catalog raw --json '.components' -; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + BATCH_COUNT))
        echo "Batch $BATCH_NUM: successfully cataloged $BATCH_COUNT components"
    else
        FAIL_COUNT=$((FAIL_COUNT + BATCH_COUNT))
        echo "Batch $BATCH_NUM: FAILED to catalog $BATCH_COUNT components" >&2
        # Continue with next batch instead of aborting
    fi
done

# Summary
echo ""
echo "Cataloging complete for $ORG_NAME"
echo "  Total batches: $BATCH_NUM"
echo "  Succeeded: $SUCCESS_COUNT components"
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "  Failed: $FAIL_COUNT components" >&2
    exit 1
fi
