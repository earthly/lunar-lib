#!/usr/bin/env bash
# Emit the CHANGELOG section for a release, derived from the commits in the
# range — the same `git log <prev-tag>..HEAD` range releasing.md already uses to
# draft the GitHub release notes. One source, two renderings.
#
#   scripts/gen-changelog-section.sh v1.16.0            # preview on stdout
#   scripts/gen-changelog-section.sh v1.16.0 --write    # splice into CHANGELOG.md
#
# Why generated rather than hand-appended: the old flow had every PR append
# under `## [Unreleased]` and a roll PR rename that heading at release time. A
# PR branched before the roll was written against `[Unreleased]`'s `### Fixed`
# list; the roll inserted `## [X.Y.Z]` directly above that same list, so the PR
# merged into the released section with no conflict and nothing to flag it. Six
# entries landed under an already-shipped heading that way. With no
# `[Unreleased]` there is no append point to race on.
#
# Bucketing is inferred from the commit subject, so treat the output as a draft:
# reconcile it against the release notes you write by hand and move any misfiled
# line before committing.
set -euo pipefail

REPO_URL="https://github.com/earthly/lunar-lib"

version=""
write=0
since=""
date=""

while [ $# -gt 0 ]; do
  case "$1" in
    --write)  write=1; shift ;;
    --since)  since="${2:?--since needs a tag}"; shift 2 ;;
    --date)   date="${2:?--date needs YYYY-MM-DD}"; shift 2 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    -*)       echo "unknown flag: $1" >&2; exit 2 ;;
    *)        version="$1"; shift ;;
  esac
done

if ! [[ "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "usage: $(basename "$0") <vX.Y.Z> [--write] [--since <tag>] [--date <YYYY-MM-DD>]" >&2
  exit 2
fi

bare="${version#v}"
[ -n "$date" ] || date="$(date -u +%F)"

if [ -z "$since" ]; then
  # Highest existing version, not `git describe`: release.sh puts the "Pin
  # images" commit on the release branch, so a release tag is never an ancestor
  # of main and describe finds nothing from here.
  since="$(git tag --list 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -1)"
  [ -n "$since" ] || { echo "no release tags found" >&2; exit 1; }
fi

# Release branches share their name with the tag (release.sh pushes both), so a
# bare `v1.15.1..HEAD` is ambiguous and git resolves it with a warning. Always
# go through refs/tags/.
range="refs/tags/${since}..HEAD"
git rev-parse --verify --quiet "refs/tags/${since}" >/dev/null \
  || { echo "no such tag: $since" >&2; exit 1; }

added=""; changed=""; fixed=""; security=""

while IFS= read -r subject; do
  # The pin commit is release mechanics, and the legacy roll PRs only moved text
  # around inside this file. Neither is a user-visible change.
  case "$subject" in
    "Pin images for v"*) continue ;;
    *CHANGELOG:*)        continue ;;
  esac

  # Public repo: ticket ids and workflow markers stay out of the file.
  entry="$subject"
  while [[ "$entry" =~ ^\[(ENG-[0-9]+|Implementation|Spec\ Only|Spec)\](.*)$ ]]; do
    entry="${BASH_REMATCH[2]}"
  done
  entry="${entry# }"
  [ -n "$entry" ] || continue

  lower="$(printf '%s' "$entry" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    *secret*|*cve*|*vulnerab*|*security*|*plaintext*)              security+="- ${entry}"$'\n' ;;
    add\ *|new\ *|*:\ add\ *|*:\ new\ *|*" add "*collector*|*" add "*policy*|*" add "*cataloger*)
                                                                   added+="- ${entry}"$'\n' ;;
    fix\ *|*:\ fix*|*" no longer "*|*" stop "*|*"don't "*|*"do not "*|*" instead of "*|*fail*|*broken*|*wrong*)
                                                                   fixed+="- ${entry}"$'\n' ;;
    *)                                                             changed+="- ${entry}"$'\n' ;;
  esac
done < <(git log --no-merges --format='%s' "$range")

section="## [${bare}] — ${date}"$'\n'
for pair in "Added:$added" "Changed:$changed" "Fixed:$fixed" "Security:$security"; do
  heading="${pair%%:*}"
  body="${pair#*:}"
  [ -n "$body" ] || continue
  section+=$'\n'"### ${heading}"$'\n\n'"${body}"
done

if [ "$section" = "## [${bare}] — ${date}"$'\n' ]; then
  echo "no user-visible commits in ${range}" >&2
  exit 1
fi

link="[${bare}]: ${REPO_URL}/compare/${since}...${version}"

if [ "$write" -eq 0 ]; then
  printf '%s\n%s\n' "$section" "$link"
  exit 0
fi

changelog="$(git rev-parse --show-toplevel)/CHANGELOG.md"
grep -q "^## \[${bare}\]" "$changelog" && { echo "CHANGELOG.md already has a [${bare}] section" >&2; exit 1; }

# Splice: the section goes above the newest existing version heading, the link
# above the newest existing link reference.
awk -v section="$section" -v link="$link" '
  !done_section && /^## \[/ { printf "%s\n", section; done_section = 1 }
  !done_link && /^\[[0-9]+\.[0-9]+\.[0-9]+\]: / { print link; done_link = 1 }
  { print }
  END {
    if (!done_section || !done_link) { print "splice failed: CHANGELOG.md structure changed" > "/dev/stderr"; exit 1 }
  }
' "$changelog" > "${changelog}.tmp"

mv "${changelog}.tmp" "$changelog"
echo "CHANGELOG.md: added [${bare}]" >&2
