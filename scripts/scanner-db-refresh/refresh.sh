#!/usr/bin/env bash
# Rebuild a released grype or trivy image with today's vulnerability DB and,
# with --push, publish it as earthly/lunar-lib:<scanner>-<release>-<YYYYMMDDHHMM>.
#
# The new image is the release-day image plus one layer, written by the
# release's own scanner binary, holding the DB. Scripts, binary and DB schema
# stay the release's. A new scanner version still ships in a lunar-lib release.
# <scanner>-<release> itself is never re-pushed.
#
# Usage: refresh.sh <grype|trivy> <vX.Y.Z> [--push]
set -euo pipefail

SCANNER=${1:-}
RELEASE=${2:-}
PUSH=${3:-}
REPO=earthly/lunar-lib
MAX_DB_AGE_HOURS=36
BASE_LABEL=org.opencontainers.image.base.digest

[[ "$SCANNER" =~ ^(grype|trivy)$ ]] || { echo "usage: $0 <grype|trivy> <vX.Y.Z> [--push]" >&2; exit 2; }
[[ "$RELEASE" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "not a release version: $RELEASE" >&2; exit 2; }
[ -z "$PUSH" ] || [ "$PUSH" = --push ] || { echo "unknown option: $PUSH" >&2; exit 2; }

TAG="$SCANNER-$RELEASE"
STAMP=$(date -u +%Y%m%d%H%M)
HERE=$(cd "$(dirname "$0")" && pwd)
CANDIDATE="scanner-db-refresh:$TAG-$STAMP"

log() { echo "[$TAG] $*" >&2; }
fail() { log "FAIL: $*"; exit 1; }

TOKEN=$(curl -fsS "https://auth.docker.io/token?service=registry.docker.io&scope=repository:$REPO:pull" | jq -r .token)
ACCEPT='application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'
registry() { curl -fsSL -H "Authorization: Bearer $TOKEN" -H "Accept: $ACCEPT" "https://registry-1.docker.io/v2/$REPO/$1"; }

# HEAD, which Docker Hub doesn't count as a pull.
remote_digest() {
  curl -fsSI -H "Authorization: Bearer $TOKEN" -H "Accept: $ACCEPT" \
    "https://registry-1.docker.io/v2/$REPO/manifests/$1" | tr -d '\r' |
    awk -F': ' 'tolower($1) == "docker-content-digest" { print $2 }'
}

newest_refresh_tag() {
  local url="https://hub.docker.com/v2/namespaces/earthly/repositories/lunar-lib/tags?name=$TAG-&page_size=100" page
  while [ -n "$url" ] && [ "$url" != null ]; do
    page=$(curl -fsS "$url")
    jq -r --arg p "$TAG-" '.results[].name | select(startswith($p) and (ltrimstr($p) | test("^[0-9]{12}$")))' <<<"$page"
    url=$(jq -r .next <<<"$page")
  done | sort | tail -n 1
}

# The base is the image the release shipped. The first refresh reads it off
# <tag>. Later ones carry it forward in a label, so a rebuild pushed to the
# release branch afterwards never becomes the base.
LAST=$(newest_refresh_tag)
if [ -n "$LAST" ]; then
  BASE=$(registry "manifests/$LAST" | jq -r .config.digest | xargs -I{} curl -fsSL -H "Authorization: Bearer $TOKEN" \
    "https://registry-1.docker.io/v2/$REPO/blobs/{}" | jq -r --arg l "$BASE_LABEL" '.config.Labels[$l] // empty')
  [ -n "$BASE" ] || fail "$LAST has no $BASE_LABEL label"
  CURRENT=$(remote_digest "$TAG")
  [ "$CURRENT" = "$BASE" ] || log "warning: $TAG now points at $CURRENT; refreshing the release-day image $BASE"
else
  BASE=$(remote_digest "$TAG")
  [ -n "$BASE" ] || fail "no $REPO:$TAG on Docker Hub"
fi
log "base $REPO@$BASE"

docker pull -q "$REPO@$BASE" >/dev/null
docker build --pull=false --build-arg BASE="$REPO@$BASE" \
  --label "org.opencontainers.image.base.name=docker.io/$REPO:$TAG" \
  --label "$BASE_LABEL=$BASE" \
  -f "$HERE/Dockerfile.$SCANNER" -t "$CANDIDATE" "$HERE" >&2

# 1. The release image plus exactly one layer.
BASE_LAYERS=$(docker image inspect "$REPO@$BASE" --format '{{json .RootFS.Layers}}')
docker image inspect "$CANDIDATE" --format '{{json .RootFS.Layers}}' |
  jq -e --argjson b "$BASE_LAYERS" '($b | length) as $n | length == $n + 1 and .[0:$n] == $b' >/dev/null ||
  fail "the candidate is not the release image plus one layer"

# 2. The release's scanner binary, byte for byte.
bin_sum() { docker run --rm --network none --entrypoint sh "$1" -c "sha256sum \"\$(command -v $SCANNER)\"" | cut -d' ' -f1; }
[ "$(bin_sum "$REPO@$BASE")" = "$(bin_sum "$CANDIDATE")" ] || fail "the $SCANNER binary changed"

# 3. A DB built in the last MAX_DB_AGE_HOURS.
if [ "$SCANNER" = grype ]; then
  BUILT=$(docker run --rm --network none --entrypoint grype "$CANDIDATE" db status -o json | jq -r .built)
else
  BUILT=$(docker run --rm --network none --entrypoint sh "$CANDIDATE" -c 'cat "$HOME/.cache/trivy/db/metadata.json"' | jq -r .UpdatedAt)
  JAVA_BUILT=$(docker run --rm --network none --entrypoint sh "$CANDIDATE" -c 'cat "$HOME/.cache/trivy/java-db/metadata.json"' | jq -r .UpdatedAt)
  [ $(( $(date -u +%s) - $(date -u -d "$JAVA_BUILT" +%s) )) -le $(( MAX_DB_AGE_HOURS * 3600 )) ] ||
    fail "Java DB built $JAVA_BUILT, more than ${MAX_DB_AGE_HOURS}h ago"
fi
[ $(( $(date -u +%s) - $(date -u -d "$BUILT" +%s) )) -le $(( MAX_DB_AGE_HOURS * 3600 )) ] ||
  fail "DB built $BUILT, more than ${MAX_DB_AGE_HOURS}h ago"
log "DB built $BUILT"

# 4. Offline, with no DB flags (as the release scripts run it), the scanner
#    still finds Log4Shell, so trivy would fail here if it tried to download a
#    DB. grype's dir: scan reads the pom.xml; trivy reads the jar as a rootfs,
#    which also loads the Java DB.
FIXTURE=$(mktemp -d)
python3 - "$FIXTURE" <<'PY'
import sys, zipfile
with zipfile.ZipFile(f"{sys.argv[1]}/log4j-core-2.14.1.jar", "w") as z:
    z.writestr("META-INF/maven/org.apache.logging.log4j/log4j-core/pom.properties",
               "groupId=org.apache.logging.log4j\nartifactId=log4j-core\nversion=2.14.1\n")
PY
cat >"$FIXTURE/pom.xml" <<'POM'
<project><modelVersion>4.0.0</modelVersion><groupId>x</groupId><artifactId>x</artifactId><version>1</version>
<dependencies><dependency><groupId>org.apache.logging.log4j</groupId><artifactId>log4j-core</artifactId><version>2.14.1</version></dependency></dependencies></project>
POM
if [ "$SCANNER" = grype ]; then
  FOUND=$(docker run --rm --network none -e GRYPE_DB_AUTO_UPDATE=false -e GRYPE_DB_VALIDATE_AGE=false \
    -v "$FIXTURE:/fixture:ro" --entrypoint grype "$CANDIDATE" dir:/fixture -o json |
    jq -r '[.matches[] | .vulnerability.id, .relatedVulnerabilities[]?.id] | index("CVE-2021-44228") != null')
else
  FOUND=$(docker run --rm --network none -v "$FIXTURE:/fixture:ro" --entrypoint trivy "$CANDIDATE" \
    rootfs --scanners vuln --format json /fixture |
    jq -r '[.Results[]?.Vulnerabilities[]?.VulnerabilityID] | index("CVE-2021-44228") != null')
fi
[ "$FOUND" = true ] || fail "the offline fixture scan did not find CVE-2021-44228"
log "offline fixture scan found CVE-2021-44228"

if [ "$PUSH" = --push ]; then
  docker tag "$CANDIDATE" "$REPO:$TAG-$STAMP"
  docker push -q "$REPO:$TAG-$STAMP" >&2
  log "pushed $REPO:$TAG-$STAMP@$(remote_digest "$TAG-$STAMP")"
else
  log "validated $CANDIDATE (not pushed)"
fi
