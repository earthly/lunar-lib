#!/usr/bin/env bash
# Print every image ref `earthly --push +all` publishes for a given tag, one per
# line, sorted.
#
# Read out of the Earthfiles rather than reconstructed from directory names: the
# tag is not the plugin directory (policies/dependencies publishes
# earthly/lunar-lib:policy-dependencies-$VERSION), so a name-derived list is
# wrong for at least one plugin and silently drifts as plugins are added.
# `+lint`'s validate_earthfile_wiring.py guarantees every plugin image target is
# wired into +all, so every SAVE IMAGE --push line found here is a ref CI pushes.
#
# Used by CI to tell the Hub which images to CVE-scan, and by hand to check a
# release published everything:
#   scripts/pushed-image-refs.sh v1.15.1 | while read -r r; do docker manifest inspect "$r" >/dev/null || echo "MISSING $r"; done
set -euo pipefail

tag="${1:-}"
if [ -z "$tag" ]; then
  echo "usage: $(basename "$0") <tag>   # e.g. main, v1.15.1, a git sha" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

# No `grep -r --include` — BusyBox grep (the base plugin image) has neither.
# shellcheck disable=SC2016  # $VERSION is literal Earthfile text, not an expansion
refs=$(find . -name Earthfile -type f -exec \
         grep -hoE 'SAVE IMAGE --push earthly/lunar-lib:[a-z0-9-]+-\$VERSION' {} + \
       | sed 's|^SAVE IMAGE --push ||' | sort -u)

if [ -z "$refs" ]; then
  echo "no 'SAVE IMAGE --push earthly/lunar-lib:<name>-\$VERSION' lines in any Earthfile — has the format changed?" >&2
  exit 1
fi

echo "${refs//\$VERSION/$tag}"
