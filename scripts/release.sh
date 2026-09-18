#!/usr/bin/env bash
set -euo pipefail

OPEN_CHANGELOG_BRANCH=1
if [ "${1:-}" = "--no-changelog-branch" ]; then
    OPEN_CHANGELOG_BRANCH=0
    shift
fi

VERSION="${1:?Usage: $0 [--no-changelog-branch] <version> (e.g. v0.1.0)}"

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

ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Creating release branch $VERSION from current HEAD..."
git checkout -b "$VERSION"

# Generate the CHANGELOG section before the pin commit, so the tag carries it --
# consumers pinning @$VERSION read the file at that ref. Bucketing is inferred
# from commit subjects, so reconcile it against the release notes you write.
echo "Generating CHANGELOG section for $VERSION..."
CHANGELOG_UPDATED=0
if "$SCRIPT_DIR/gen-changelog-section.sh" "$VERSION" --write; then
    CHANGELOG_UPDATED=1
else
    echo "WARNING: no CHANGELOG section generated -- releasing without one" >&2
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

# The release branch is never merged back, so main needs the section too. It is
# generated and nothing else touches the file, so this branch cannot conflict.
CHANGELOG_BRANCH=""
if [ "$CHANGELOG_UPDATED" -eq 1 ] && [ "$OPEN_CHANGELOG_BRANCH" -eq 1 ]; then
    CHANGELOG_BRANCH="release-changelog-$VERSION"
    git checkout -q -b "$CHANGELOG_BRANCH"
    # refs/tags/, not "$VERSION": the release branch and tag share a name.
    git checkout "refs/tags/$VERSION" -- CHANGELOG.md
    git commit -q -m "CHANGELOG: record $VERSION" CHANGELOG.md
    git push -q -u origin "$CHANGELOG_BRANCH"
    git checkout -q "$ORIGINAL_BRANCH"
fi

echo ""
echo "Release $VERSION created and pushed (branch + tag)."
echo "CI will build and push images tagged $VERSION."
echo "Consumers pin with: @$VERSION"
if [ -n "$CHANGELOG_BRANCH" ]; then
    echo ""
    echo "CHANGELOG section is on the tag. main still needs it -- open the PR:"
    echo "  <pr-tool> --base main --head $CHANGELOG_BRANCH --title \"CHANGELOG: record $VERSION\""
fi
