#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?Usage: $0 <version> (e.g. v0.1.0)}"

if ! [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: version must be v-prefixed semver (e.g. v0.1.0)" >&2
    exit 1
fi

if [[ "$OSTYPE" == darwin* ]]; then
    SED_INPLACE=(sed -i '')
else
    SED_INPLACE=(sed -i)
fi

if git show-ref --verify --quiet "refs/heads/$VERSION" 2>/dev/null || \
   git ls-remote --exit-code --heads origin "$VERSION" >/dev/null 2>&1; then
    echo "Error: branch $VERSION already exists" >&2
    exit 1
fi

if git show-ref --verify --quiet "refs/tags/$VERSION" 2>/dev/null || \
   git ls-remote --exit-code --tags origin "$VERSION" >/dev/null 2>&1; then
    echo "Error: tag $VERSION already exists" >&2
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "Error: working directory is not clean" >&2
    exit 1
fi

# CI's release gate runs `lunar policy ok-release` on HEAD before pushing any
# image, and fails if main never recorded HEAD's images for Lunar to scan. Check
# that record now, so a release doesn't leave behind a tag that can never publish.
HEAD_SHA=$(git rev-parse HEAD)
if ! command -v gh >/dev/null 2>&1; then
    echo "Error: gh is required to confirm main's CI recorded the images for $HEAD_SHA" >&2
    exit 1
fi
RECORD=$(gh api "repos/earthly/lunar-lib/commits/$HEAD_SHA/check-runs?check_name=record%20pushed%20images%20for%20CVE%20scan" \
    --jq '.check_runs[0] | if . == null then "missing" else (.conclusion // .status) end' 2>/dev/null) || RECORD="unreadable"
if [ "$RECORD" != "success" ]; then
    echo "Error: main's 'record pushed images for CVE scan' for $HEAD_SHA is '$RECORD', not success" >&2
    echo "Release a main commit whose CI finished; Lunar can't vet images it never scanned." >&2
    exit 1
fi

# Every image builds FROM earthly/lunar-scripts, which bakes the lunar CLI and OS
# packages, so a release must ship the newest one. Bumping on main (Renovate's
# "lunar-scripts base" PR) keeps the images the release gate scanned the shipped ones.
if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq is required to look up the newest earthly/lunar-scripts release" >&2
    exit 1
fi
SCRIPTS_TOKEN=$(curl -fsSL "https://auth.docker.io/token?service=registry.docker.io&scope=repository:earthly/lunar-scripts:pull" | jq -r .token) || SCRIPTS_TOKEN=""
LATEST_SCRIPTS=$(curl -fsSL -H "Authorization: Bearer $SCRIPTS_TOKEN" "https://registry-1.docker.io/v2/earthly/lunar-scripts/tags/list?n=1000" \
    | jq -er '[.tags[] | select(test("^[0-9]+\\.[0-9]+\\.[0-9]+$")) | split(".") | map(tonumber)] | max | map(tostring) | join(".")' 2>/dev/null) || LATEST_SCRIPTS=""
if [ -z "$LATEST_SCRIPTS" ]; then
    echo "Error: couldn't look up the newest earthly/lunar-scripts release on Docker Hub" >&2
    exit 1
fi
SCRIPTS_PINS=$(grep -rnE --include=Earthfile '^[[:space:]]*ARG SCRIPTS_VERSION(_DEBIAN)?=' . || true)
if [ -z "$SCRIPTS_PINS" ]; then
    echo "Error: found no SCRIPTS_VERSION pins in any Earthfile" >&2
    exit 1
fi
STALE_PINS=$(echo "$SCRIPTS_PINS" | grep -vE "=${LATEST_SCRIPTS//./\\.}-(alpine|debian)[[:space:]]*$" || true)
if [ -n "$STALE_PINS" ]; then
    echo "Error: these lunar-scripts pins are behind the newest release, $LATEST_SCRIPTS:" >&2
    echo "$STALE_PINS" >&2
    echo "Bump them on main and release that commit." >&2
    exit 1
fi

ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Creating release branch $VERSION from current HEAD..."
git checkout -b "$VERSION"

# Only the tag carries the full CHANGELOG.md (the previous tag's file plus this
# section): consumers pinning @$VERSION read it at that ref, and main's copy is
# just a pointer to the releases, so nothing goes back to main.
echo "Generating CHANGELOG section for $VERSION..."
if ! "$SCRIPT_DIR/gen-changelog-section.sh" "$VERSION" --write; then
    echo "WARNING: no CHANGELOG section generated -- releasing without one" >&2
fi
if ! grep -q '^## \[' CHANGELOG.md; then
    echo "ERROR: CHANGELOG.md has no release sections -- refusing to tag main's pointer" >&2
    exit 1
fi

echo "Rewriting manifests: -main → -$VERSION..."
while IFS= read -r -d '' file; do
    "${SED_INPLACE[@]}" "s|earthly/lunar-lib:\(.*\)-main|earthly/lunar-lib:\1-${VERSION}|g" "$file"
done < <(find . -name 'lunar-*.yml' -print0)

# Verify no earthly/lunar-lib images still reference -main
if grep -r 'earthly/lunar-lib:.*-main' --include='lunar-*.yml' .; then
    echo "ERROR: found unrewritten -main image references" >&2
    exit 1
fi

echo "Rewriting starter-pack refs → @$VERSION..."
while IFS= read -r -d '' file; do
    "${SED_INPLACE[@]}" "s|github://earthly/lunar-lib/\([^@]*\)@[^[:space:]]*|github://earthly/lunar-lib/\1@${VERSION}|g" "$file"
done < <(find . -path '*/starter-packs/*' -name '*.yml' -print0)

# Verify all starter-pack refs now point at the target version
if grep -E 'github://earthly/lunar-lib/[^@]+@' ./starter-packs/ -r --include='*.yml' | grep -v "@${VERSION}"; then
    echo "ERROR: found starter-pack references not pinned to $VERSION" >&2
    exit 1
fi

git add -A
git commit -m "Pin images for $VERSION"

echo "Tagging $VERSION..."
git tag "$VERSION"

git push -u origin "refs/heads/$VERSION:refs/heads/$VERSION"
git push origin "refs/tags/$VERSION:refs/tags/$VERSION"

git checkout "$ORIGINAL_BRANCH"

echo ""
echo "Release $VERSION created and pushed (branch + tag)."
echo "CI will build and push images tagged $VERSION."
echo "Consumers pin with: @$VERSION"
