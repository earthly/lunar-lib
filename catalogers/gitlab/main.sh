#!/bin/bash
set -euo pipefail

# GitLab Cataloger — discovers the groups the service account maintains and
# catalogs their projects, including subgroups, as Lunar components.

# Inputs. Every one repeats its manifest default, because `lunar cataloger dev`
# runs in a sanitized env that does not apply manifest defaults.
GITLAB_HOST_RAW="${LUNAR_VAR_GITLAB_HOST:-gitlab.com}"
GITLAB_HOST=$(echo "$GITLAB_HOST_RAW" | sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://##; s#/.*$##')
GITLAB_HOST="${GITLAB_HOST:-gitlab.com}"
API_BASE="${LUNAR_VAR_API_BASE_URL:-}"
API_BASE="${API_BASE:-https://${GITLAB_HOST}/api/v4}"
API_BASE="${API_BASE%/}"

INCLUDE_PUBLIC="${LUNAR_VAR_INCLUDE_PUBLIC:-true}"
INCLUDE_INTERNAL="${LUNAR_VAR_INCLUDE_INTERNAL:-true}"
INCLUDE_PRIVATE="${LUNAR_VAR_INCLUDE_PRIVATE:-true}"
INCLUDE_ARCHIVED="${LUNAR_VAR_INCLUDE_ARCHIVED:-false}"
INCLUDE_FORKS="${LUNAR_VAR_INCLUDE_FORKS:-true}"
INCLUDE_PERSONAL_NAMESPACES="${LUNAR_VAR_INCLUDE_PERSONAL_NAMESPACES:-false}"
INCLUDE_PROJECTS="${LUNAR_VAR_INCLUDE_PROJECTS:-}"
EXCLUDE_PROJECTS="${LUNAR_VAR_EXCLUDE_PROJECTS:-}"
ALLOWED_TOPICS="${LUNAR_VAR_ALLOWED_TOPICS:-}"
DISALLOWED_TOPICS="${LUNAR_VAR_DISALLOWED_TOPICS:-}"
# `-` not `:-`: an explicit empty tag_prefix must survive so it can disable
# prefixing, which is documented behavior.
TAG_PREFIX="${LUNAR_VAR_TAG_PREFIX-gl-}"
DEFAULT_OWNER="${LUNAR_VAR_DEFAULT_OWNER:-}"
DEFAULT_DOMAIN="${LUNAR_VAR_DEFAULT_DOMAIN:-}"
DOMAIN_FROM_GROUP_PATH="${LUNAR_VAR_DOMAIN_FROM_GROUP_PATH:-false}"

# Maintainer. Fixed, not an input: this is the Hub's own scope signal, and a
# lower level would onboard groups whose webhooks can never be registered.
MIN_ACCESS_LEVEL=40

PER_PAGE=100
MAX_RETRIES=5
INITIAL_BACKOFF=5
BATCH_SIZE=1000
# Pace when the remaining API budget gets this low rather than driving into a 429.
RATE_LIMIT_FLOOR=20

GL_TOKEN="${LUNAR_SECRET_GL_TOKEN:-}"
if [ -z "$GL_TOKEN" ]; then
    # Deliberately exit 1, not the usual exit-0-on-missing-secret. A cataloger
    # that exits 0 having written nothing reports an empty estate, and absence
    # is what retires components — so a missing token would retire the whole
    # catalog instead of leaving yesterday's in place.
    echo "Error: LUNAR_SECRET_GL_TOKEN is not set. Configure the GL_TOKEN secret at cataloger scope: lunar secret set GL_TOKEN --scope cataloger" >&2
    exit 1
fi

WORK=/tmp/gitlab-cataloger
rm -rf "$WORK"; mkdir -p "$WORK"

echo "Cataloging GitLab projects from $GITLAB_HOST"
echo "API base: $API_BASE"
echo "Include archived: $INCLUDE_ARCHIVED"
echo "Include forks: $INCLUDE_FORKS"
echo "Include personal namespaces: $INCLUDE_PERSONAL_NAMESPACES"
[ -n "$INCLUDE_PROJECTS" ] && echo "Include patterns: $INCLUDE_PROJECTS"
[ -n "$EXCLUDE_PROJECTS" ] && echo "Exclude patterns: $EXCLUDE_PROJECTS"
[ -n "$ALLOWED_TOPICS" ] && echo "Allowed topics: $ALLOWED_TOPICS"
[ -n "$DISALLOWED_TOPICS" ] && echo "Disallowed topics: $DISALLOWED_TOPICS"
[ -n "$DEFAULT_OWNER" ] && echo "Default owner: $DEFAULT_OWNER"
[ -n "$DEFAULT_DOMAIN" ] && echo "Default domain: $DEFAULT_DOMAIN"
[ "$DOMAIN_FROM_GROUP_PATH" = "true" ] && echo "Domain from group path: enabled"

# --- HTTP -------------------------------------------------------------------

# gl_api <path-with-query> <out-file>
# Writes the response body to <out-file>. Retries 429 and 5xx honoring
# Retry-After; aborts the run on any other non-2xx, because shrinking the
# reported project set is what silently retires components.
gl_api() {
    local path="$1" out="$2"
    local attempt=1 backoff=$INITIAL_BACKOFF code hdr="$WORK/hdr"

    while [ "$attempt" -le "$MAX_RETRIES" ]; do
        code=$(curl -sS -o "$out" -D "$hdr" -w '%{http_code}' \
            -H "PRIVATE-TOKEN: ${GL_TOKEN}" \
            -H 'Accept: application/json' \
            "${API_BASE}${path}" 2>>"$WORK/curl.err") || code="000"

        case "$code" in
            2*)
                # Pace against the documented budget instead of discovering it via a 429.
                local remaining reset now sleep_for
                remaining=$(sed -n 's/^[Rr]ate[Ll]imit-[Rr]emaining:[[:space:]]*\([0-9]*\).*/\1/p' "$hdr" | tail -1)
                if [ -n "$remaining" ] && [ "$remaining" -le "$RATE_LIMIT_FLOOR" ]; then
                    reset=$(sed -n 's/^[Rr]ate[Ll]imit-[Rr]eset:[[:space:]]*\([0-9]*\).*/\1/p' "$hdr" | tail -1)
                    now=$(date +%s)
                    if [ -n "$reset" ] && [ "$reset" -gt "$now" ]; then
                        sleep_for=$((reset - now + 1))
                        [ "$sleep_for" -gt 60 ] && sleep_for=60
                        echo "Rate limit budget at $remaining, sleeping ${sleep_for}s until reset" >&2
                        sleep "$sleep_for"
                    fi
                fi
                return 0
                ;;
            429|5*|000)
                local retry_after
                retry_after=$(sed -n 's/^[Rr]etry-[Aa]fter:[[:space:]]*\([0-9]*\).*/\1/p' "$hdr" | tail -1)
                [ -n "$retry_after" ] && backoff="$retry_after"
                echo "HTTP $code on $path (attempt $attempt/$MAX_RETRIES), retrying in ${backoff}s" >&2
                sleep "$backoff"
                backoff=$((backoff * 2))
                attempt=$((attempt + 1))
                ;;
            *)
                echo "Error: HTTP $code on $path — aborting rather than reporting a partial estate." >&2
                head -c 500 "$out" >&2; echo >&2
                exit 1
                ;;
        esac
    done

    echo "Error: $path still failing after $MAX_RETRIES attempts — aborting rather than reporting a partial estate." >&2
    exit 1
}

urlenc_path() { printf '%s' "$1" | sed 's#/#%2F#g'; }

# --- filters ----------------------------------------------------------------

glob_to_regex() {
    local escaped
    escaped=$(echo "$1" | sed -E 's/([.+^${}()|\\])/\\\1/g')
    escaped=$(echo "$escaped" | sed 's/\*/.\*/g; s/?/./g')
    echo "^${escaped}$"
}

patterns_to_regex() {
    local patterns="$1" pattern
    [ -z "$patterns" ] && { echo ""; return; }
    local parts=()
    IFS=',' read -ra arr <<< "$patterns"
    for pattern in "${arr[@]}"; do
        pattern=$(echo "$pattern" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')
        [ -n "$pattern" ] && parts+=("$(glob_to_regex "$pattern")")
    done
    local IFS='|'
    echo "${parts[*]}"
}

INCLUDE_REGEX=$(patterns_to_regex "$INCLUDE_PROJECTS")
EXCLUDE_REGEX=$(patterns_to_regex "$EXCLUDE_PROJECTS")

VISIBILITIES=""
[ "$INCLUDE_PUBLIC" = "true" ]   && VISIBILITIES="${VISIBILITIES}public "
[ "$INCLUDE_INTERNAL" = "true" ] && VISIBILITIES="${VISIBILITIES}internal "
[ "$INCLUDE_PRIVATE" = "true" ]  && VISIBILITIES="${VISIBILITIES}private "
if [ -z "$VISIBILITIES" ]; then
    echo "Error: at least one of include_public / include_internal / include_private must be true" >&2
    exit 1
fi
echo "Visibilities: $VISIBILITIES"

# --- group discovery --------------------------------------------------------

# /groups ignores id_after (verified against gitlab.com), so this endpoint is
# offset-paginated. Bounded by group count rather than project count, so paging
# by page=N is cheap here — but it is still walked to the end, never truncated.
echo "Discovering top-level groups (maintainer or above)..."
: > "$WORK/groups.txt"
page=1
while :; do
    gl_api "/groups?top_level_only=true&min_access_level=${MIN_ACCESS_LEVEL}&per_page=${PER_PAGE}&page=${page}&order_by=id&sort=asc" \
        "$WORK/groups-page.json"
    n=$(jq 'length' "$WORK/groups-page.json")
    [ "$n" -eq 0 ] && break
    jq -r '.[].full_path' "$WORK/groups-page.json" >> "$WORK/groups.txt"
    [ "$n" -lt "$PER_PAGE" ] && break
    page=$((page + 1))
done

GROUP_COUNT=$(wc -l < "$WORK/groups.txt" | tr -d ' ')
echo "Discovered $GROUP_COUNT top-level group(s): $(tr '\n' ' ' < "$WORK/groups.txt")"
if [ "$GROUP_COUNT" -eq 0 ]; then
    # Nothing to report is not the same as "the estate is empty" — the token may
    # have lost its memberships. Writing an empty catalog here would retire
    # every component, so refuse instead.
    echo "Error: the token's account maintains no top-level groups on $GITLAB_HOST. Refusing to write an empty catalog." >&2
    exit 1
fi

# --- project enumeration ----------------------------------------------------

# Keyset via id_after. NOTE: pagination=keyset is silently ignored on this
# endpoint (it still returns offset Link headers), so id_after is what makes
# the paging actually keyset — do not switch to following Link: rel="next".
ARCHIVED_PARAM=""
[ "$INCLUDE_ARCHIVED" != "true" ] && ARCHIVED_PARAM="&archived=false"

: > "$WORK/projects.ndjson"
while IFS= read -r group; do
    [ -z "$group" ] && continue
    enc=$(urlenc_path "$group")
    after=0
    pages=0
    before=$(wc -l < "$WORK/projects.ndjson" | tr -d ' ')
    while :; do
        # with_shared=false: GitLab includes projects shared INTO the group by
        # default, which are owned elsewhere — they would be cataloged outside
        # the account's groups and duplicated across any group sharing them.
        gl_api "/groups/${enc}/projects?include_subgroups=true&with_shared=false&per_page=${PER_PAGE}&order_by=id&sort=asc&id_after=${after}${ARCHIVED_PARAM}" \
            "$WORK/proj-page.json"
        n=$(jq 'length' "$WORK/proj-page.json")
        [ "$n" -eq 0 ] && break
        jq -c --arg g "$group" '.[] | {id, path_with_namespace, description, topics: (.topics // .tag_list // []), archived, visibility, default_branch, group: $g, namespace_kind: .namespace.kind, pending_deletion: ((.marked_for_deletion_on // .marked_for_deletion_at) != null), is_fork: has("forked_from_project"), forked_from: (.forked_from_project.path_with_namespace // null)}' \
            "$WORK/proj-page.json" >> "$WORK/projects.ndjson"
        after=$(jq -r '.[-1].id' "$WORK/proj-page.json")
        pages=$((pages + 1))
    done
    now=$(wc -l < "$WORK/projects.ndjson" | tr -d ' ')
    echo "  $group: $((now - before)) project(s) over $pages page(s)"
done < "$WORK/groups.txt"

# Personal (user) namespaces are invisible to the group sweep by construction —
# a personal namespace is not a group — so they need their own pass. Scoped with
# membership=true on purpose: plain /projects on an instance-admin token returns
# every project on the instance, including every user's scratch repos.
if [ "$INCLUDE_PERSONAL_NAMESPACES" = "true" ]; then
    echo "Sweeping personal namespaces the account is a member of..."
    after=0
    pages=0
    before=$(wc -l < "$WORK/projects.ndjson" | tr -d ' ')
    while :; do
        gl_api "/projects?membership=true&per_page=${PER_PAGE}&order_by=id&sort=asc&id_after=${after}${ARCHIVED_PARAM}" \
            "$WORK/personal-page.json"
        n=$(jq 'length' "$WORK/personal-page.json")
        [ "$n" -eq 0 ] && break
        # Keep only user namespaces: the group projects in this listing are the
        # ones the group sweep already has, and re-adding them would duplicate.
        jq -c '.[] | select(.namespace.kind == "user")
               | {id, path_with_namespace, description, topics: (.topics // .tag_list // []), archived, visibility, default_branch, group: .namespace.full_path, namespace_kind: .namespace.kind, pending_deletion: ((.marked_for_deletion_on // .marked_for_deletion_at) != null), is_fork: has("forked_from_project"), forked_from: (.forked_from_project.path_with_namespace // null)}' \
            "$WORK/personal-page.json" >> "$WORK/projects.ndjson"
        after=$(jq -r '.[-1].id' "$WORK/personal-page.json")
        pages=$((pages + 1))
    done
    now=$(wc -l < "$WORK/projects.ndjson" | tr -d ' ')
    echo "  personal namespaces: $((now - before)) project(s) over $pages page(s)"
fi

TOTAL_FETCHED=$(wc -l < "$WORK/projects.ndjson" | tr -d ' ')
echo "Total projects fetched: $TOTAL_FETCHED"

# --- transform --------------------------------------------------------------

jq -s \
    --arg host "$GITLAB_HOST" \
    --arg prefix "$TAG_PREFIX" \
    --arg owner "$DEFAULT_OWNER" \
    --arg domain "$DEFAULT_DOMAIN" \
    --arg domain_from_path "$DOMAIN_FROM_GROUP_PATH" \
    --arg include_regex "$INCLUDE_REGEX" \
    --arg exclude_regex "$EXCLUDE_REGEX" \
    --arg visibilities "$VISIBILITIES" \
    --arg include_forks "$INCLUDE_FORKS" \
    --arg allowed_topics "$ALLOWED_TOPICS" \
    --arg disallowed_topics "$DISALLOWED_TOPICS" \
    '
    # GitLab topics are free text (any ASCII bar linebreaks). Whitespace and
    # parens are exactly the token boundaries in the boolexpr lexer, so a tag
    # containing either makes the whole on: expression a parse error, not just
    # that term; matching is also case-sensitive. Other punctuation lexes fine.
    def norm: ascii_downcase | gsub("[\\s()]+"; "-") | gsub("-+"; "-") | gsub("^-+|-+$"; "");
    def csv_set($s): ($s | split(",") | map(norm) | map(select(length > 0)));

    (csv_set($allowed_topics)) as $allow |
    (csv_set($disallowed_topics)) as $deny |
    ($visibilities | split(" ") | map(select(length > 0))) as $vis |

    [ .[]
      | select(.visibility as $v | $vis | index($v))
      | select(($include_regex == "") or (.path_with_namespace | test($include_regex)))
      | select(($exclude_regex == "") or (.path_with_namespace | test($exclude_regex) | not))
      | select($include_forks == "true" or (.is_fork | not))
      # A GitLab delete is delayed: it renames the project to
      # <path>-deletion_scheduled-<id> and keeps listing it, archived still
      # false, until the retention window expires. Cataloging it would keep a
      # component alive under a mangled name for weeks after the delete.
      # Either field satisfies it: gitlab.com currently returns both
      # marked_for_deletion_on and _at in agreement, and reading only one would
      # silently stop filtering if that one is the half that goes away.
      | select(.pending_deletion | not)
      | . + {norm_topics: [(.topics // [])[] | norm] }
      # allow ∩ topics, expressed as set difference twice
      | select(($allow | length) == 0 or (($allow - ($allow - .norm_topics)) | length) > 0)
      | select(($deny  | length) == 0 or (($deny  - ($deny  - .norm_topics)) | length) == 0)
    ]
    # Domain from the group path: the namespace containing the project becomes
    # a dotted domain, with default_domain as the root when both are set. A dot
    # inside a GitLab path segment would invent a hierarchy level that is not
    # there, so it is folded to a dash.
    | [ .[] | . + {derived_domain: (
          if $domain_from_path != "true" then $domain
          else
            ((.path_with_namespace | split("/") | .[:-1] | map(gsub("\\."; "-")))
             | (if $domain != "" then [$domain] + . else . end)
             | join("."))
          end
        )} ]
    | [ .[] | {
        key: "\($host)/\(.path_with_namespace)",
        value: (
          {
            tags: (
              ([.norm_topics[] | "\($prefix)\(.)"] | unique)
              + ["gitlab-visibility-\(.visibility)"]
              + (if .archived then ["gitlab-archived"] else [] end)
              + (if .is_fork  then ["gitlab-fork"]     else [] end)
              + (if .namespace_kind == "user" then ["gitlab-personal-namespace"] else [] end)
            ),
            meta: (
              {
                visibility: .visibility,
                archived: (if .archived then "true" else "false" end),
                project_id: (.id | tostring),
                group: .group,
                fork: (if .is_fork then "true" else "false" end),
                namespace_kind: .namespace_kind,
              }
              # Absent rather than empty: a project with no commits has no
              # default branch, and an undescribed project has no description.
              + (if (.description // "") != "" then {description: .description} else {} end)
              + (if (.default_branch // "") != "" then {default_branch: .default_branch} else {} end)
              + (if (.topics // []) != [] then {topics: (.topics | join(","))} else {} end)
              + (if .forked_from != null then {forked_from: .forked_from} else {} end)
            )
          }
          + (if $owner != "" then {owner: $owner} else {} end)
          + (if .derived_domain != "" then {domain: .derived_domain} else {} end)
        )
      } ]
    ' "$WORK/projects.ndjson" > "$WORK/entries.json"

TOTAL=$(jq 'length' "$WORK/entries.json")
echo "Components after filtering: $TOTAL"

if [ "$TOTAL" -eq 0 ]; then
    # Every project filtered out is a configuration answer, not an outage, so
    # this one is allowed to be an empty report — but say so loudly, because the
    # consequence is that the previous catalog contribution is retired.
    echo "WARNING: no projects matched the configured filters; this run reports an empty catalog and will retire any components a previous run contributed." >&2
    exit 0
fi

# --- write ------------------------------------------------------------------

# Register domains BEFORE the components that reference them: the hub resolves
# a component's domain against the declared set and DROPS the component when it
# is missing, and batches are saved as they are written. Derived domains make
# this load-bearing rather than a formality — there is one per group path.
jq -r '[.[].value.domain // empty] | unique | .[]' "$WORK/entries.json" > "$WORK/domains.txt"
DOMAIN_COUNT=$(wc -l < "$WORK/domains.txt" | tr -d ' ')
if [ "$DOMAIN_COUNT" -gt 0 ]; then
    echo "Registering $DOMAIN_COUNT domain(s): $(tr '\n' ' ' < "$WORK/domains.txt")"
    jq -R -s 'split("\n") | map(select(length > 0))
              | map({(.): {description: "Created by the gitlab cataloger"}}) | add' \
        "$WORK/domains.txt" \
        | lunar catalog raw --json '.domains' -
fi

batch=0
start=0
while [ "$start" -lt "$TOTAL" ]; do
    batch=$((batch + 1))
    count=$BATCH_SIZE
    [ $((start + count)) -gt "$TOTAL" ] && count=$((TOTAL - start))
    echo "Writing batch $batch: components $((start + 1))-$((start + count)) of $TOTAL"
    jq --argjson s "$start" --argjson c "$count" '.[$s:$s + $c] | from_entries' "$WORK/entries.json" \
        | lunar catalog raw --json '.components' -
    start=$((start + count))
done

echo "Cataloged $TOTAL component(s) from $GROUP_COUNT group(s) on $GITLAB_HOST"
