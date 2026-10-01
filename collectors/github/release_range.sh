#!/bin/bash

# LUNAR_COMPONENT_* / LUNAR_SECRET_* / LUNAR_VAR_* are injected by the Lunar
# runtime — they are not local assignments or typos of each other. The
# single-quoted $names are GraphQL and jq variables, not shell expansions.
# shellcheck disable=SC2153,SC2016
set -e

# Records the commits the evaluated default-branch commit would release: every
# commit since the previous release tag, each with its signature verification
# and the merged pull request that brought it in (with that PR's approvals).
# Opt-in: does nothing until release_tag_pattern is set.

PATTERN="${LUNAR_VAR_RELEASE_TAG_PATTERN-}"
MAX_COMMITS="${LUNAR_VAR_RELEASE_RANGE_MAX_COMMITS:-250}"
HEAD_SHA="${LUNAR_COMPONENT_GIT_SHA:-}"

if [ -z "$PATTERN" ]; then
  echo "release_tag_pattern is not set; skipping release range collection." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "LUNAR_SECRET_GH_TOKEN is not set; skipping release range collection. Configure the GH_TOKEN secret for this collector." >&2
  exit 0
fi

if [ -z "$HEAD_SHA" ]; then
  echo "LUNAR_COMPONENT_GIT_SHA is not set; skipping release range collection." >&2
  exit 0
fi

if ! jq -n --arg re "$PATTERN" '"" | test($re)' > /dev/null 2>&1; then
  echo "Error: release_tag_pattern is not a valid regular expression: ${PATTERN}" >&2
  exit 1
fi

case "$MAX_COMMITS" in
  '' | *[!0-9]*)
    echo "Error: release_range_max_commits must be a positive integer, got: ${MAX_COMMITS}" >&2
    exit 1
    ;;
esac
# Strip leading zeros (bash reads 0250 as octal, and 08 not at all), and cap at
# 1000: GitHub lists only the newest 1000 commits of a comparison.
MAX_COMMITS="${MAX_COMMITS#"${MAX_COMMITS%%[!0]*}"}"
if [ -z "$MAX_COMMITS" ]; then
  echo "Error: release_range_max_commits must be a positive integer, got: ${LUNAR_VAR_RELEASE_RANGE_MAX_COMMITS}" >&2
  exit 1
fi
if [ "${#MAX_COMMITS}" -gt 4 ] || [ "$MAX_COMMITS" -gt 1000 ]; then
  echo "release_range_max_commits capped at 1000, the most commits GitHub lists for a comparison." >&2
  MAX_COMMITS=1000
fi

# Component IDs are <host>/<owner>/<repository>[/<subpath>...]. Keep only
# owner/repository, and route GHES hosts to /api/graphql.
HOST="${LUNAR_COMPONENT_ID%%/*}"
REST="${LUNAR_COMPONENT_ID#*/}"
OWNER="${REST%%/*}"
REST="${REST#*/}"
NAME="${REST%%/*}"

GRAPHQL_URL="https://api.github.com/graphql"
if [ "$HOST" != "github.com" ]; then
  GRAPHQL_URL="https://${HOST}/api/graphql"
fi

# POST a GraphQL query ($1) with variables ($2, a JSON object) and print .data.
# Retries transient failures. Returns non-zero on any other HTTP error or when
# the response carries errors, so a partial answer is never recorded.
gql() {
  local payload resp code body attempt=1
  payload=$(jq -cn --arg q "$1" --argjson v "$2" '{query: $q, variables: $v}')
  while :; do
    resp=$(printf '%s' "$payload" | curl -sSL -w $'\n%{http_code}' -X POST \
      -H "Authorization: bearer ${LUNAR_SECRET_GH_TOKEN}" \
      -H "Content-Type: application/json" \
      --data-binary @- "$GRAPHQL_URL" 2>/dev/null) || resp=$'\n000'
    code=$(printf '%s\n' "$resp" | tail -n1)
    case "$code" in
      000 | 429 | 5[0-9][0-9])
        if [ "$attempt" -lt 3 ]; then
          sleep "$attempt"
          attempt=$((attempt + 1))
          continue
        fi
        ;;
    esac
    break
  done
  body=$(printf '%s\n' "$resp" | sed '$d')
  if [ "$code" != "200" ]; then
    echo "GitHub GraphQL API returned HTTP ${code}." >&2
    return 1
  fi
  if ! printf '%s' "$body" | jq -e '(.errors // []) | length == 0' > /dev/null 2>&1; then
    printf '%s' "$body" | jq -r '.errors[]?.message // "unparseable response"' 2>/dev/null \
      | sed 's/^/GitHub GraphQL error: /' >&2
    return 1
  fi
  printf '%s' "$body" | jq -c '.data'
}

# 1. Release-tag candidates: the 10 most recent tags (by commit date) matching
#    the pattern.
TAGS_QUERY='query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { name }
    refs(refPrefix: "refs/tags/", first: 100, after: $cursor,
         orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { name target { oid ... on Tag { target { oid } } } }
    }
  }
}'

CANDIDATES='[]'
CURSOR=null
DEFAULT_BRANCH=""
for _ in 1 2 3 4 5; do
  VARS=$(jq -cn --arg owner "$OWNER" --arg name "$NAME" --argjson cursor "$CURSOR" \
    '{owner: $owner, name: $name, cursor: $cursor}')
  if ! DATA=$(gql "$TAGS_QUERY" "$VARS"); then
    echo "Error: could not list the tags of ${OWNER}/${NAME}." >&2
    exit 1
  fi
  if [ "$(printf '%s' "$DATA" | jq '.repository == null')" = "true" ]; then
    echo "Error: repository ${OWNER}/${NAME} not found or not visible to the token." >&2
    exit 1
  fi
  DEFAULT_BRANCH=$(printf '%s' "$DATA" | jq -r '.repository.defaultBranchRef.name // empty')
  CANDIDATES=$(printf '%s\n%s\n' "$CANDIDATES" "$DATA" | jq -cs --arg re "$PATTERN" \
    '(.[0] + [.[1].repository.refs.nodes[] | select(.name | test($re))
      | {tag: .name, sha: (.target.target.oid // .target.oid)}])[:10]')
  [ "$(printf '%s' "$CANDIDATES" | jq 'length')" -lt 10 ] || break
  [ "$(printf '%s' "$DATA" | jq '.repository.refs.pageInfo.hasNextPage')" = "true" ] || break
  CURSOR=$(printf '%s' "$DATA" | jq -c '.repository.refs.pageInfo.endCursor')
done

emit() {
  printf '%s' "$1" | lunar collect -j ".vcs.release_range" -
}

if [ "$(printf '%s' "$CANDIDATES" | jq 'length')" = "0" ]; then
  echo "No tag matches release_tag_pattern '${PATTERN}'; no previous release to bound the range." >&2
  emit "$(jq -cn --arg p "$PATTERN" --arg h "$HEAD_SHA" '{tag_pattern: $p, head_sha: $h}')"
  exit 0
fi

# 2. The previous release is the candidate that leaves the fewest commits
#    ahead of it. Comparing against the tag's merge base handles release tags
#    cut on a release branch; a tag at or after HEAD leaves none and is skipped.
FIELDS=$(printf '%s' "$CANDIDATES" | jq -r 'to_entries
  | map("t\(.key): ref(qualifiedName: $t\(.key)) { compare(headRef: $head) { aheadBy } }") | join("\n    ")')
DECLS=$(printf '%s' "$CANDIDATES" | jq -r 'to_entries | map(", $t\(.key): String!") | join("")')
COMPARE_QUERY="query(\$owner: String!, \$name: String!, \$head: String!${DECLS}) {
  repository(owner: \$owner, name: \$name) {
    ${FIELDS}
  }
}"
VARS=$(printf '%s' "$CANDIDATES" | jq -c --arg owner "$OWNER" --arg name "$NAME" --arg head "$HEAD_SHA" \
  '{owner: $owner, name: $name, head: $head}
   + (to_entries | map({key: "t\(.key)", value: "refs/tags/\(.value.tag)"}) | from_entries)')
if ! DATA=$(gql "$COMPARE_QUERY" "$VARS"); then
  echo "Error: could not compare the release tags of ${OWNER}/${NAME} with ${HEAD_SHA}." >&2
  exit 1
fi
BASE=$(printf '%s\n%s\n' "$CANDIDATES" "$DATA" | jq -cs '
  .[0] as $tags | .[1].repository as $cmp
  | [$tags | to_entries[] | . as $e | {tag: $e.value.tag, sha: $e.value.sha,
      ahead: ($cmp["t\($e.key)"].compare.aheadBy // 0)} | select(.ahead > 0)]
  | min_by(.ahead) // empty | {tag, sha}')

if [ -z "$BASE" ]; then
  echo "No tag matching release_tag_pattern '${PATTERN}' precedes ${HEAD_SHA}; no previous release to bound the range." >&2
  emit "$(jq -cn --arg p "$PATTERN" --arg h "$HEAD_SHA" '{tag_pattern: $p, head_sha: $h}')"
  exit 0
fi

# 3. The range itself, oldest first (of the newest 1000 for a longer range):
#    signature state, and the merged pull request that introduced each commit,
#    with that PR's approvals.
RANGE_QUERY='query($owner: String!, $name: String!, $base: String!, $head: String!,
               $first: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    ref(qualifiedName: $base) {
      compare(headRef: $head) {
        commits(first: $first, after: $cursor) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes {
            oid
            author { name user { login } }
            signature { isValid state }
            associatedPullRequests(first: 5) {
              nodes {
                number merged mergedAt baseRefName headRefName headRefOid
                mergedBy { __typename login }
                reviews(first: 50, states: [APPROVED]) {
                  nodes { author { __typename login } submittedAt commit { oid } }
                }
              }
            }
          }
        }
      }
    }
  }
}'

# GraphQL signature states are REST's verification reasons in upper case, bar
# two abbreviations, and GraphQL drops the "[bot]" suffix REST logins carry;
# map both so .vcs.pr and this range agree.
COMMIT_FILTER='def login: if . == null then null
    elif .__typename == "Bot" then "\(.login)[bot]" else .login end;
  [.[] | ({sha: .oid, author: (.author.user.login // .author.name)} | with_entries(select(.value != null)))
  + {signature: (if .signature == null then {verified: false, reason: "unsigned"}
      else {verified: .signature.isValid,
            reason: (.signature.state | ascii_downcase
              | if . == "malformed_sig" then "malformed_signature"
                elif . == "unknown_sig_type" then "unknown_signature_type"
                else . end)} end)}
  + ([.associatedPullRequests.nodes[]? | select(.merged)]
     | (map(select(.baseRefName == $default)) + .) | first
     | if . == null then {} else {pull_request: ({
         number, base_branch: .baseRefName, head_branch: .headRefName, merged_at: .mergedAt,
         merged_by: (.mergedBy | login), head_sha: .headRefOid,
         approvals: [.reviews.nodes[]?
           | {reviewer: ((.author | login) // "ghost"), submitted_at: .submittedAt, commit_sha: .commit.oid}
           | with_entries(select(.value != null))]
       } | with_entries(select(.value != null)))} end)]'

BASE_TAG=$(printf '%s' "$BASE" | jq -r '.tag')
COMMITS='[]'
TOTAL=0
CURSOR=null
while :; do
  REMAINING=$((MAX_COMMITS - $(printf '%s' "$COMMITS" | jq 'length')))
  [ "$REMAINING" -gt 0 ] || break
  [ "$REMAINING" -le 100 ] || REMAINING=100
  VARS=$(jq -cn --arg owner "$OWNER" --arg name "$NAME" --arg base "refs/tags/${BASE_TAG}" \
    --arg head "$HEAD_SHA" --argjson first "$REMAINING" --argjson cursor "$CURSOR" \
    '{owner: $owner, name: $name, base: $base, head: $head, first: $first, cursor: $cursor}')
  if ! DATA=$(gql "$RANGE_QUERY" "$VARS"); then
    echo "Error: could not list the commits between ${BASE_TAG} and ${HEAD_SHA}." >&2
    exit 1
  fi
  PAGE=$(printf '%s' "$DATA" | jq -c '.repository.ref.compare.commits // empty')
  if [ -z "$PAGE" ]; then
    echo "Error: GitHub could not compare ${BASE_TAG} with ${HEAD_SHA}." >&2
    exit 1
  fi
  TOTAL=$(printf '%s' "$PAGE" | jq '.totalCount')
  COMMITS=$(printf '%s\n%s\n' "$COMMITS" "$(printf '%s' "$PAGE" \
    | jq -c --arg default "$DEFAULT_BRANCH" ".nodes | ${COMMIT_FILTER}")" | jq -cs 'add')
  [ "$(printf '%s' "$PAGE" | jq '.pageInfo.hasNextPage')" = "true" ] || break
  CURSOR=$(printf '%s' "$PAGE" | jq -c '.pageInfo.endCursor')
done

emit "$(printf '%s\n%s\n' "$BASE" "$COMMITS" | jq -cs --arg p "$PATTERN" --arg h "$HEAD_SHA" \
  --arg default "$DEFAULT_BRANCH" --argjson total "$TOTAL" '{tag_pattern: $p, head_sha: $h,
    default_branch: $default, base: .[0], total_commits: $total,
    truncated: ($total > (.[1] | length)), commits: .[1]}')"
