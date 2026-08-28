#!/bin/bash
set -eo pipefail

# =============================================================================
# CodeQL monorepo fan-out
# =============================================================================
#
# PROBLEM
# Repo-scoped scanners — CodeQL default setup is the canonical one — analyse a
# whole repository and report findings tagged with a repo-relative file path.
# In a monorepo the Lunar components are the *subdirectories*
# (github.com/org/repo/services/api), while the traced scan resolves to the
# *repo* (github.com/org/repo). The scan data therefore lands on a component the
# subcomponents' SAST policies never read, and every subcomponent evaluates as
# "No SAST scanning data found" even though its code was scanned.
#
# WHAT THIS DOES
# Runs on the monorepo ROOT component once its collection settles, reads the
# repo-wide findings the scanner already produced (.sast.issues), and
# redistributes them to the repo's subcomponents by file path — writing each
# subcomponent's own slice onto its Component JSON at the same commit, through
# the hub's out-of-band collect path.
#
# HOOK CHOICE — why .sast.issues and not .sast
# The after-json hook fires when its `path` is PRESENT in the settled merged
# blob (hub/afterjson/afterjson.go, Match). Hooking `.sast` — or
# `.sast.native.codeql` — would fire on any codeql invocation at all, because
# the CodeQL CLI collector writes .sast.native.codeql.cicd.cmds for EVERY exec:
# `database init`, `resolve languages`, `finalize`, `bundle`, `cleanup`, none of
# which produce findings. .sast.issues is written only once a SARIF report has
# actually been parsed, so it is the first key in the chain whose presence
# guarantees there is a path-tagged payload to fan out.
#
# PATH ATTRIBUTION — reuses Lunar's own rule, no new concept
# A finding is attributed to a subcomponent when its file matches that
# subcomponent's path patterns, under exactly the rule the hub already uses to
# decide "does this changed file affect this component":
# util/git.ComponentPathPatterns (the explicit `paths:` plus the implicit
# "<subdir>/*" the component name itself implies) matched with util/str.MatchStar
# (a trailing "*" is a prefix match, anything else is exact). So a shared file a
# subcomponent explicitly claims — say `.github/workflows/ci.yml` — carries its
# findings to every subcomponent that claims it, consistent with how a change to
# that file already re-evaluates all of them.
#
# Findings that match no subcomponent (repo-root files, unclaimed directories)
# stay on the root component only.
#
# CROSS-COMPONENT WRITES
# See .ai-implementation/cross-component-collection.md. The traps that apply
# here are handled below: LUNAR_COLLECT_STDOUT must be unset or --component is
# silently ignored and the write lands back on self; CollectExternal appends
# rather than upserts, so each write is fingerprint-guarded; and an empty
# self-reference is fatal rather than something to run through.
# =============================================================================

log() { echo "codeql.monorepo-fanout: $*" >&2; }

# --- 0. Self-reference and dimensions ----------------------------------------
# A cross-component writer keys every decision off its own component name. If
# that were empty the subcomponent filter below would degenerate to "every
# component in the catalog", so bail rather than run with a broken self-ref.
ROOT="${LUNAR_COMPONENT_ID:-}"
if [ -z "$ROOT" ]; then
  log "LUNAR_COMPONENT_ID is empty — refusing to run a cross-component writer with no self-reference"
  exit 0
fi

# CollectExternal is keyed by (component, sha) and validates a 40-hex SHA, so
# without one there is nothing to write against.
SHA="${LUNAR_COMPONENT_GIT_SHA:-}"
if [ -z "$SHA" ]; then
  log "LUNAR_COMPONENT_GIT_SHA is empty — cannot target an out-of-band write"
  exit 0
fi

# LUNAR_COMPONENT_ID, LUNAR_COMPONENT_GIT_SHA and LUNAR_COMPONENT_PR are all
# injected by the Lunar runtime from the run's dimensions
# (util/env.dimensionEnvMap); PR is absent on a default-branch run.
# shellcheck disable=SC2153
PR="${LUNAR_COMPONENT_PR:-}"

# Reads and writes are both pinned to the exact (sha, pr) this wave settled on.
# Unpinned, `get-json` resolves the default-branch snapshot (`WHERE pr IS NULL`)
# — a different commit — which is what made the container scan read the wrong
# blob for months (lunar-lib#284).
read_dims=(--git-sha "$SHA")
write_dims=(--sha "$SHA")
if [ -n "$PR" ]; then
  read_dims+=(--pr "$PR")
  write_dims+=(--pr "$PR")
fi

MAX_TARGETS="${LUNAR_VAR_MAX_SUBCOMPONENTS:-50}"
# jq needs a real boolean, and the input arrives as a string.
case "${LUNAR_VAR_INCLUDE_ISSUES:-false}" in
  true|True|TRUE|yes|1) INCLUDE_ISSUES=true ;;
  *)                    INCLUDE_ISSUES=false ;;
esac

log "root=$ROOT sha=${SHA:0:8} pr=${PR:-none}"

# Hub reads are retried for several MINUTES, and a persistent failure is FATAL
# rather than a quiet exit 0.
#
# Why so long: the wave fires when COLLECTION settles, but `lunar component
# get-json` reads through `public.components` / `public.components_latest`,
# and both are views over `mat.components` + `mat.component_json` — BASE TABLES
# drained asynchronously by the hub's mat workers. A SHA-pinned read needs THIS
# commit's row to have drained; until it does the lookup simply returns
# NotFound. Measured on cronos: 210s of NotFound after the wave had already
# fired and failed. A 20s budget was nowhere near enough.
#
# Falling back to the UNPINNED read would be wrong, not merely lax. It resolves
# `components_latest ... WHERE pr IS NULL`, which succeeds immediately — but by
# returning whichever older commit HAS drained. During that same window it
# returned the PREVIOUS DAY's commit. The fan-out would then have written those
# stale findings under this commit's SHA. Pinning is correct; waiting is the
# price.
#
# And the failure has to be loud: the after-json wave is fire-once per
# (component, sha, pr) forever, so a swallowed read permanently loses this
# commit's fan-out and no re-run can recover it. exit 1 puts it in the run
# listing where an operator can see it and push a new commit.
READ_BUDGET_SECS="${LUNAR_VAR_READ_RETRY_SECONDS:-300}"

retry_read() {
  local out attempt=0 waited=0 backoff
  while :; do
    attempt=$((attempt + 1))
    if out=$("$@" 2>/dev/null) && [ -n "$out" ]; then
      [ "$attempt" -gt 1 ] && log "read succeeded on attempt $attempt after ${waited}s"
      printf '%s' "$out"
      return 0
    fi
    backoff=$((attempt * 5))
    [ "$backoff" -gt 30 ] && backoff=30
    [ $((waited + backoff)) -gt "$READ_BUDGET_SECS" ] && return 1
    sleep "$backoff"
    waited=$((waited + backoff))
  done
}

# --- 1. Discover the subcomponents -------------------------------------------
# Deliberately BEFORE reading our own Component JSON, so a component that is not
# a monorepo root costs one cheap scoped query and exits — rather than a
# (retried, up to READ_BUDGET_SECS) get-json for data it will never use. This
# collector is meant to be targeted at monorepo roots via `on:`; the early exit
# is the safety net, not the intended configuration.
#
# Scoped SQL query, NOT `lunar cataloger get-json`. The merged-catalog RPC
# returns the WHOLE catalog as one uncompressed gRPC message — 6.2 MB / ~30k
# components on our own dogfood hub — to find the handful of names under one
# repo. It blows the gRPC client message cap (`ResourceExhausted: received
# message larger than max (6264541 vs 4194304)`, ENG-1648) and is wasteful even
# when it fits, since the size scales with the whole fleet rather than this repo.
#
# `public.catalog_latest` is the SQL-API view over the same catalog, so Postgres
# does the prefix filter server-side and only the matching rows cross the wire.
# It also carries each component's explicit `paths:` (catalog_latest.sql builds
# them into the document), which is what makes accurate attribution possible.
discover_subcomponents() {
  local conn
  conn=$(retry_read lunar sql connection-string) || return 1
  psql "$conn" --no-align --tuples-only --quiet --field-separator=$'\t' -c "
      SELECT c.key, COALESCE(c.value->'paths', '[]'::jsonb)::text
      FROM public.catalog_latest, jsonb_each(catalog_json->'components') c
      WHERE c.key LIKE '$(printf '%s' "$ROOT" | sed "s/'/''/g")/%'
      ORDER BY c.key" 2>/dev/null |
    jq -R -s -c 'split("\n") | map(select(length > 0) | split("\t"))
                 | map({key: .[0], value: {paths: (.[1] | fromjson)}})
                 | {components: from_entries}'
}

if ! CATALOG=$(discover_subcomponents) || [ -z "$CATALOG" ]; then
  log "ERROR: could not enumerate subcomponents of $ROOT via the SQL API. The wave is fire-once, so this commit's fan-out is lost — check that the Hub's SQL API is reachable from collectors."
  exit 1
fi

SUBCOMPONENT_COUNT=$(echo "$CATALOG" | jq '.components | length')
if [ "$SUBCOMPONENT_COUNT" -eq 0 ]; then
  log "$ROOT has no subcomponents — not a monorepo root, nothing to fan out. Target this collector at monorepo roots with \`on:\` to avoid running it here at all."
  exit 0
fi

# --- 2. Read the repo-wide findings ------------------------------------------
if ! ROOT_JSON=$(retry_read lunar component get-json "$ROOT" "${read_dims[@]}"); then
  log "ERROR: could not read own Component JSON at ${SHA:0:8} within ${READ_BUDGET_SECS}s. This commit's row is most likely not yet materialized (mat.components / mat.component_json drain asynchronously, so a SHA-pinned read lags collection). The wave is fire-once, so this commit's fan-out is lost — push a new commit once ingestion catches up."
  exit 1
fi

# Absent .sast.issues means no scanner produced a path-tagged finding list for
# this commit. An EMPTY list is a different thing and IS fanned out — see the
# note on zero-finding subcomponents in step 4.
if ! echo "$ROOT_JSON" | jq -e '(.sast // {}) | has("issues")' >/dev/null 2>&1; then
  log "no .sast.issues at this commit — nothing to fan out"
  exit 0
fi

ISSUES=$(echo "$ROOT_JSON" | jq -c '.sast.issues // []')
SOURCE=$(echo "$ROOT_JSON" | jq -c '.sast.source // {}')
log "root carries $(echo "$ISSUES" | jq 'length') SAST issue(s), $SUBCOMPONENT_COUNT subcomponent(s) discovered"

# --- 3. Attribute each finding to the subcomponents that own its file --------
TARGETS=$(jq -n -c \
  --arg root "$ROOT" \
  --argjson issues "$ISSUES" \
  --argjson catalog "$CATALOG" '
  # util/str.MatchStar: trailing "*" is a prefix match, anything else exact.
  def match_star($pat): . as $val
    | if ($pat | endswith("*")) then ($val | startswith($pat[0:-1])) else ($val == $pat) end;

  # util/git.ComponentPathPatterns: the explicit paths plus the implicit
  # "<subdir>/*" that the component name itself implies.
  def patterns($name; $explicit):
    ($name | ltrimstr($root + "/")) as $subdir
    | ($explicit // [])
    | if   ($subdir == "")                    then .
      elif (index($subdir + "/*") != null)    then .
      else . + [$subdir + "/*"] end;

  # Severity counts in the shape .sast.findings uses.
  def counts:
    (group_by(.severity) | map({key: (.[0].severity // "unknown"), value: length}) | from_entries) as $g
    | { critical: ($g.critical // 0), high: ($g.high // 0),
        medium: ($g.medium // 0), low: ($g.low // 0), total: length };

  [ (($catalog.components // {}) | to_entries[])
    | select(.key != $root and (.key | startswith($root + "/")))
    | { name: .key, patterns: patterns(.key; .value.paths) }
  ]
  # A pattern-less target would inherit PathIntersects'"'"'s "empty matches
  # everything" and silently receive the whole repo. Drop it instead.
  | map(select(.patterns | length > 0))
  | sort_by(.name)
  | map(
      . as $t
      | [ $issues[]
          | . as $iss
          | select($iss.file != null
                   and ($t.patterns | any(. as $p | $iss.file | match_star($p)))) ] as $mine
      | ($mine | counts) as $c
      | { name:     $t.name,
          patterns: $t.patterns,
          issues:   $mine,
          findings: $c,
          summary:  { has_critical: ($c.critical > 0), has_high: ($c.high > 0) } }
    )')

TARGET_COUNT=$(echo "$TARGETS" | jq 'length')
if [ "$TARGET_COUNT" -eq 0 ]; then
  # Distinct from the "no subcomponents" exit above: those exist, but every one
  # of them was dropped for having no usable path pattern, so there is nothing
  # to attribute findings against.
  log "all $SUBCOMPONENT_COUNT subcomponent(s) of $ROOT were dropped for having no path patterns — nothing to fan out"
  exit 0
fi

# Bound the blast radius, and say so out loud rather than truncating silently.
if [ "$TARGET_COUNT" -gt "$MAX_TARGETS" ]; then
  log "WARNING: $TARGET_COUNT subcomponents exceeds max_subcomponents=$MAX_TARGETS — fanning out to the first $MAX_TARGETS by name and SKIPPING the rest"
  TARGETS=$(echo "$TARGETS" | jq -c ".[:$MAX_TARGETS]")
  TARGET_COUNT="$MAX_TARGETS"
fi

log "discovered $TARGET_COUNT subcomponent(s)"

# --- 4. Write each subcomponent's slice --------------------------------------
# Zero-finding subcomponents ARE written. The repo-wide scan genuinely covered
# their code, so "0 findings" is a positive result: it is what turns their SAST
# policy from "No SAST scanning data found" into a pass. Skipping them would
# leave exactly the gap this collector exists to close.
RESULTS="[]"
i=0
while [ "$i" -lt "$TARGET_COUNT" ]; do
  TARGET=$(echo "$TARGETS" | jq -c ".[$i]")
  i=$((i + 1))

  NAME=$(echo "$TARGET" | jq -r '.name')
  MATCHED=$(echo "$TARGET" | jq '.issues | length')

  # Fingerprint the exact payload so a re-fired wave is a no-op. CollectExternal
  # APPENDS a record per call and the hub merge concatenates arrays across
  # records, so an unguarded re-run would duplicate every issue.
  FINGERPRINT=$(echo "$TARGET" | jq -c '{issues, findings}' | sha256sum | cut -c1-32)

  TARGET_JSON=$(lunar component get-json "$NAME" "${read_dims[@]}" 2>/dev/null || echo "")

  if [ -n "$TARGET_JSON" ]; then
    # Never overwrite a subcomponent's OWN scan. A per-service scan is more
    # precise than a repo-wide one, so if this component already has SAST data
    # from anything other than a previous fan-out, leave it alone.
    OWN=$(echo "$TARGET_JSON" | jq -r '.sast.source.integration // ""')
    if [ -n "$OWN" ] && [ "$OWN" != "monorepo-fanout" ]; then
      log "skip $NAME — already has its own SAST scan (integration=$OWN)"
      RESULTS=$(echo "$RESULTS" | jq -c --arg n "$NAME" --arg r "own-scan:$OWN" '. + [{component: $n, status: "skipped", reason: $r}]')
      continue
    fi

    # The fingerprint alone is NOT enough to conclude "already written for this
    # commit". A SHA-pinned `get-json` is not SHA-exact: when a component has no
    # collection of its own at that SHA the Hub carries the previous commit's
    # blob forward, so the read happily returns an OLDER commit's fan-out —
    # matching fingerprint and all. Observed on cronos: at sha f50924dc every
    # target was skipped as "unchanged" against provenance written at e3dd3d09,
    # and `hub.merged_collection_blobs` had no row at f50924dc at all.
    #
    # Provenance already records which commit produced it, so require that too.
    # Same payload for the SAME commit is a genuine no-op worth skipping (the
    # wave can re-fire); same payload carried forward from a DIFFERENT commit is
    # this commit never having been written.
    PRIOR=$(echo "$TARGET_JSON" | jq -r '.sast.source.fanout.fingerprint // ""')
    PRIOR_SHA=$(echo "$TARGET_JSON" | jq -r '.sast.source.fanout.root_git_sha // ""')
    if [ "$PRIOR" = "$FINGERPRINT" ] && [ "$PRIOR_SHA" = "$SHA" ]; then
      log "skip $NAME — already carries this exact fan-out for ${SHA:0:8} (fingerprint $FINGERPRINT)"
      RESULTS=$(echo "$RESULTS" | jq -c --arg n "$NAME" '. + [{component: $n, status: "skipped", reason: "unchanged"}]')
      continue
    fi
  fi

  # What a subcomponent gets is deliberately SMALL: the counts its SAST policies
  # actually evaluate, plus provenance. Two reasons.
  #
  # 1. `.native` stays on the ROOT only. The raw SARIF the scanner produced
  #    (.sast.native.codeql.sarif) describes the whole repository, so copying it
  #    onto a subcomponent would be both wrong (it is not that component's data)
  #    and by far the largest thing here. The root keeps it; subcomponents get
  #    the derived numbers. Provenance therefore lives under `.sast.source`,
  #    which is the normalized "where did this come from" key, rather than
  #    inventing a `.native` entry on the target.
  # 2. `policies/sast` reads `.sast.summary.has_<sev>`, then falls back to
  #    `.sast.findings.<sev>`, and `max_total` reads `.sast.findings.total`.
  #    None of them read `.sast.issues`. Shipping the per-finding array to every
  #    subcomponent is a write whose size scales with findings x subcomponents
  #    for data no guardrail evaluates — so it is opt-in via `include_issues`
  #    for operators who want the detail visible per service.
  PAYLOAD=$(echo "$TARGET" | jq -c \
    --arg root "$ROOT" --arg sha "$SHA" --arg fp "$FINGERPRINT" \
    --argjson source "$SOURCE" --argjson with_issues "$INCLUDE_ISSUES" '
    . as $t
    | { findings: $t.findings,
        summary:  $t.summary,
        source: ($source + {
          integration: "monorepo-fanout",
          fanout: {
            root_component: $root,
            root_git_sha:   $sha,
            paths:          $t.patterns,
            matched:        ($t.issues | length),
            fingerprint:    $fp } }) }
    | if $with_issues then . + {issues: $t.issues} else . end')

  # `--component` is only honoured on a real hub submit. Inside a collector
  # runtime LUNAR_COLLECT_STDOUT makes `lunar collect` print instead, and the
  # sidecar files the result against the CURRENT component — so the fan-out
  # would silently write every subcomponent's slice onto the root.
  # stdout is discarded: the sidecar parses this script's stdout as the ROOT
  # component's collection, so anything a submit-mode collect happens to print
  # must not reach it.
  if echo "$PAYLOAD" | env -u LUNAR_COLLECT_STDOUT -u LUNAR_LOG_PREFIX \
      lunar collect --component "$NAME" "${write_dims[@]}" -j ".sast" - >/dev/null; then
    log "wrote $MATCHED issue(s) to $NAME"
    RESULTS=$(echo "$RESULTS" | jq -c --arg n "$NAME" --argjson m "$MATCHED" '. + [{component: $n, status: "written", matched: $m}]')
  else
    log "WARNING: failed to write to $NAME"
    RESULTS=$(echo "$RESULTS" | jq -c --arg n "$NAME" '. + [{component: $n, status: "failed"}]')
  fi
done

# --- 5. Breadcrumb on the root -----------------------------------------------
# A collector's stderr is not queryable from the hub, so record what the fan-out
# resolved to on the root's own JSON. When a write "doesn't land", this says why.
echo "$RESULTS" | jq -c --arg sha "$SHA" '{git_sha: $sha, targets: .}' |
  lunar collect -j ".sast.native.monorepo_fanout" -

log "done — $(echo "$RESULTS" | jq '[.[] | select(.status == "written")] | length') written, $(echo "$RESULTS" | jq '[.[] | select(.status == "skipped")] | length') skipped"
