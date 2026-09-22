#!/bin/bash
#
# moon Cataloger — dependency-paths (component-repo, clone-code).
#
# Runs once per component of a repo that just received a commit, with the
# repo checked out. Reads the moon project graph (`moon query projects`),
# finds the project whose `source` is this component's subdirectory, and
# writes `paths` = that project's own directory plus every directory it
# transitively depends on, so a change to a shared library re-evaluates the
# services that consume it.
#
# `paths` gates policy EVALUATION, not data attribution. Widening it makes a
# library change re-run a service's policies; it does not move a CI run's
# collected data onto that service.
#
# Silent skips (exit 0, no write):
#   - component is the repo root (no subdir): it already matches every path,
#     and writing paths would NARROW it
#   - no moon workspace (`.moon/`) at or above the working directory
#   - the component's subdir is not a moon project
#
# Hard failures (non-zero, no write):
#   - `moon query projects` fails or emits unparseable output
#   - the workspace has several projects but moon reports no dependency edges
#     at all, which is what an unresolvable toolchain looks like: moon exits 0
#     with an empty stderr and an edgeless graph. Publishing that would claim
#     nothing depends on anything. Set require_dependency_edges=false for a
#     workspace that genuinely declares none.
#
# Inputs (LUNAR_VAR_*): require_dependency_edges, exclude_scopes
# Secrets: none — the graph comes from the checkout.

set -euo pipefail

COMPONENT_ID="${LUNAR_COMPONENT_ID:?LUNAR_COMPONENT_ID must be set by the component-repo runner}"
REQUIRE_EDGES="${LUNAR_VAR_REQUIRE_DEPENDENCY_EDGES:-true}"
EXCLUDE_SCOPES="${LUNAR_VAR_EXCLUDE_SCOPES:-}"

echo "Component: $COMPONENT_ID"

# --- Locate the moon workspace --------------------------------------------
# moon resolves its workspace by walking up for `.moon/`, so it would find the
# root on its own. We resolve it ourselves anyway because `source` values are
# workspace-relative while `paths` must be repo-relative: when the workspace
# root sits below the repo root, every source needs that offset prefixed.
#
# The walk stops at the repo root. moon keeps its own plugin cache in
# `$HOME/.moon`, so an unbounded walk can leave the checkout, "find" that, and
# resolve sources against a directory the repo knows nothing about.
find_workspace_root() {
    local dir="$1" boundary="$2"
    while :; do
        if [ -d "$dir/.moon" ]; then
            printf '%s\n' "$dir"
            return 0
        fi
        [ "$dir" = "$boundary" ] && return 1
        [ "$dir" = "/" ] && return 1
        dir=$(dirname "$dir")
    done
}

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$REPO_ROOT" ]; then
    echo "Not inside a git checkout — skipping (this cataloger needs clone-code: true)"
    exit 0
fi
# -P on both so a symlinked mount can't defeat the prefix arithmetic below.
REPO_ROOT=$(cd "$REPO_ROOT" && pwd -P)
CWD=$(pwd -P)

# --- The component's subdirectory -----------------------------------------
# Take it from the checkout, not by parsing the component id: the hook already
# put us in the component's subdirectory (the operator appends it to the
# working dir), so `pwd` relative to the repo root IS the subdir. Parsing the
# id instead would need per-forge rules — GitLab separates a nested namespace
# from the subdir with `/-/`, so a naive "everything after the third slash"
# resolves nothing there and the cataloger would silently do nothing.
case "$CWD" in
    "$REPO_ROOT") SUBDIR="" ;;
    "$REPO_ROOT"/*) SUBDIR="${CWD#"$REPO_ROOT"/}" ;;
    *)
        echo "Working directory $CWD is not inside the checkout at $REPO_ROOT — skipping"
        exit 0 ;;
esac

if [ -z "$SUBDIR" ]; then
    echo "Component is the repo root (no subdir) — skipping: it already matches every path, and setting paths would narrow it"
    exit 0
fi
echo "Subdir: $SUBDIR"

WORKSPACE_ROOT=$(find_workspace_root "$CWD" "$REPO_ROOT" || true)
if [ -z "$WORKSPACE_ROOT" ]; then
    echo "No .moon/ between $CWD and the repo root — not a moon workspace, skipping"
    exit 0
fi
echo "Workspace root: $WORKSPACE_ROOT (repo root: $REPO_ROOT)"

# Offset of the workspace root inside the repo, as a path prefix ("" when they
# are the same directory).
WS_PREFIX="${WORKSPACE_ROOT#"$REPO_ROOT"}"
WS_PREFIX="${WS_PREFIX#/}"
[ -n "$WS_PREFIX" ] && echo "Workspace is nested at: $WS_PREFIX"

# --- Read the graph --------------------------------------------------------
# `moon query projects` prints JSON on stdout by default (there is no --json
# flag in moon 2.x). It reads moon.yml files and needs no network; a language
# toolchain is only required for edges moon infers rather than reads.
# moon unpacks its embedded toolchain plugin under $HOME (~/.moon, ~/.proto) and
# fails hard if that is not writable, which a cluster running snippet pods with
# a read-only root filesystem would hit. Give it a scratch HOME so the run does
# not depend on the pod's.
MOON_SCRATCH_HOME=$(mktemp -d)
trap 'rm -rf "$MOON_SCRATCH_HOME"' EXIT

GRAPH=$(cd "$WORKSPACE_ROOT" && HOME="$MOON_SCRATCH_HOME" moon query projects) || {
    echo "moon query projects failed in $WORKSPACE_ROOT" >&2
    exit 1
}

if ! printf '%s' "$GRAPH" | jq -e '.projects | type == "array"' >/dev/null 2>&1; then
    echo "moon query projects did not return a .projects array" >&2
    exit 1
fi

PROJECT_COUNT=$(printf '%s' "$GRAPH" | jq '.projects | length')
echo "moon reports $PROJECT_COUNT project(s)"

# --- Fail closed on an edgeless multi-project graph ------------------------
EDGE_COUNT=$(printf '%s' "$GRAPH" | jq '[.projects[].dependencies // [] | length] | add // 0')
echo "Dependency edges in graph: $EDGE_COUNT"
if [ "$EDGE_COUNT" -eq 0 ] && [ "$PROJECT_COUNT" -gt 1 ]; then
    if [ "$REQUIRE_EDGES" = "true" ]; then
        echo "moon reported $PROJECT_COUNT projects and no dependency edges at all." >&2
        echo "That is also what an unresolvable toolchain looks like — moon exits 0 with an empty stderr." >&2
        echo "Refusing to publish a graph that claims nothing depends on anything." >&2
        echo "Set require_dependency_edges=false if this workspace really declares no dependsOn." >&2
        exit 1
    fi
    echo "No dependency edges, and require_dependency_edges=false — continuing"
fi

# --- Resolve this component's paths ---------------------------------------
# One jq pass: match the project by source, walk the dependency closure
# breadth-first, and turn each reached project's source into a `<dir>/*` glob.
# Trailing `*` is a plain prefix match in the hub (util/str.MatchStar) and it
# crosses `/`, so one glob per directory covers everything beneath it.
PATHS_JSON=$(printf '%s' "$GRAPH" | jq -c \
    --arg subdir "$SUBDIR" \
    --arg prefix "$WS_PREFIX" \
    --arg excluded "$EXCLUDE_SCOPES" '
    def repo_path($source): if $prefix == "" then $source else $prefix + "/" + $source end;

    ($excluded | split(",") | map(ascii_downcase | gsub("^\\s+|\\s+$"; "")) | map(select(. != ""))) as $skip_scopes |

    # id -> repo-relative source
    (reduce .projects[] as $p ({}; .[$p.id] = repo_path($p.source))) as $source_of |

    # id -> [dependency ids], minus excluded scopes
    (reduce .projects[] as $p ({};
        .[$p.id] = [ $p.dependencies // [] | .[]
                     | select((.scope // "" | ascii_downcase) as $s | ($skip_scopes | index($s)) == null)
                     | .id ]
    )) as $deps_of |

    # the project whose source is this component
    ([.projects[] | select(repo_path(.source) == $subdir) | .id] | first) as $root |

    if $root == null then null
    else
      # breadth-first transitive closure over $deps_of
      {seen: [$root], frontier: [$root]}
      | until(.frontier == [];
          ([.frontier[] | $deps_of[.][]?] | unique) as $nbrs
          | .seen as $s
          | {seen: (($s + $nbrs) | unique), frontier: ($nbrs - $s)}
        )
      | .seen
      | map($source_of[.] // empty)
      | map(. + "/*")
      | unique
    end')

if [ "$PATHS_JSON" = "null" ]; then
    echo "No moon project has source '$SUBDIR' — component is not a moon project, skipping"
    exit 0
fi

echo "Resolved paths: $PATHS_JSON"

# --- Write -----------------------------------------------------------------
# The hub appends arrays on merge (util/maps.Merge), so these union with any
# paths declared in lunar-config.yml rather than replacing them.
printf '%s' "$PATHS_JSON" \
    | jq --arg id "$COMPONENT_ID" '{($id): {paths: .}}' \
    | lunar catalog raw --json '.components' -

echo "Wrote $(printf '%s' "$PATHS_JSON" | jq 'length') path(s) for $COMPONENT_ID"
