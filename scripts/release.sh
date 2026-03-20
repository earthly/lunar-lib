#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?Usage: $0 <version> (e.g. v0.1.0)}"

if ! [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: version must be v-prefixed semver (e.g. v0.1.0)" >&2
    exit 1
fi

if ! command -v yq &>/dev/null; then
    echo "Error: yq is required (https://github.com/mikefarah/yq)" >&2
    exit 1
fi

if ! yq --version 2>&1 | grep -q "mikefarah"; then
    echo "Error: wrong yq installed. Need mikefarah/yq." >&2
    echo "Install: https://github.com/mikefarah/yq#install" >&2
    exit 1
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

echo "Creating release branch $VERSION from current HEAD..."
git checkout -b "$VERSION"

echo "Rewriting manifests: -main → -$VERSION..."
export IMAGE_TAG="$VERSION"
find . -name 'lunar-*.yml' -exec \
    yq -i '(.. | select(tag == "!!str" and test("earthly/lunar-lib:.*-main$"))) |= sub("-main$", "-" + strenv(IMAGE_TAG))' {} \;

# Verify no earthly/lunar-lib images still reference -main
if grep -r 'earthly/lunar-lib:.*-main' --include='lunar-*.yml' .; then
    echo "ERROR: found unrewritten -main image references" >&2
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
