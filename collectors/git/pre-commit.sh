#!/bin/bash
set -e

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_PRE_COMMIT_PATHS"

CONFIG_FILE=""
for candidate in "${CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    CONFIG_FILE="./$candidate"
    break
  fi
done

if [ -z "$CONFIG_FILE" ]; then
  exit 0
fi

PATH_NORMALIZED="${CONFIG_FILE#./}"

if ! CONFIG_JSON=$(yq -o json "$CONFIG_FILE" 2>/dev/null) || [ -z "$CONFIG_JSON" ] || [ "$CONFIG_JSON" = "null" ]; then
  jq -n --arg path "$PATH_NORMALIZED" \
    '{valid: false, path: $path}' \
    | lunar collect -j ".git.pre_commit" -
  exit 0
fi

REPOS=$(echo "$CONFIG_JSON" | jq -c '
  (.repos // []) | map({
    repo: .repo,
    rev: (.rev // null),
    hooks: ((.hooks // []) | map({id: .id}))
  })
')

HOOK_IDS=$(echo "$REPOS" | jq -c '[.[].hooks[].id] | unique')
HOOK_COUNT=$(echo "$REPOS" | jq '[.[].hooks[]] | length')
REPO_COUNT=$(echo "$REPOS" | jq 'length')
CI_SKIP=$(echo "$CONFIG_JSON" | jq -c '(.ci.skip // [])')

# all_pinned: every repo has rev that's not a floating ref. The "meta" repo
# (e.g. https://github.com/pre-commit/pre-commit) is special-cased — pre-commit
# itself permits omitting rev there. Treat any other repo with no rev or a
# floating rev as not-pinned.
FLOATING_REFS_PATTERN='^(main|master|HEAD|develop|trunk)$'
ALL_PINNED=$(echo "$REPOS" | jq --arg floating "$FLOATING_REFS_PATTERN" '
  all(
    .[];
    (.repo == "meta") or
    ((.rev // "") | test($floating; "i") | not) and ((.rev // "") != "")
  )
')

jq -n \
  --arg path "$PATH_NORMALIZED" \
  --argjson repos "$REPOS" \
  --argjson hook_ids "$HOOK_IDS" \
  --argjson hook_count "$HOOK_COUNT" \
  --argjson repo_count "$REPO_COUNT" \
  --argjson ci_skip "$CI_SKIP" \
  --argjson all_pinned "$ALL_PINNED" \
  '{
    valid: true,
    path: $path,
    repos: $repos,
    hook_ids: $hook_ids,
    hook_count: $hook_count,
    repo_count: $repo_count,
    ci_skip: $ci_skip,
    all_pinned: $all_pinned
  }' | lunar collect -j ".git.pre_commit" -
