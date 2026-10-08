#!/usr/bin/env bash
# Gate every image `earthly --push +all` published at <tag>. Each one is scanned
# with grype and fails on any fixable finding at or above SCAN_FAIL_ON (default
# high), or when its lunar CLI isn't the latest lunar-dist release. Nothing is
# skipped: a missing image, a failed pull or a failed scan fails the run.
#
#   scripts/scan-images.sh <tag>    # main's short sha, a PR branch tag, or vX.Y.Z
#
# Needs docker (logged in to Docker Hub: anonymous pulls hit the rate limit),
# grype, curl and jq. GH_TOKEN, when set, authenticates the lunar-dist lookup.
# grype reads ignore rules from .grype.yaml; any entry there needs a reason.
set -euo pipefail

tag="${1:-}"
if [ -z "$tag" ]; then
  echo "usage: $(basename "$0") <tag>" >&2
  exit 2
fi
fail_on="${SCAN_FAIL_ON:-high}"
case "$fail_on" in
  critical) severities="Critical" ;;
  high) severities="Critical High" ;;
  medium) severities="Critical High Medium" ;;
  *) echo "SCAN_FAIL_ON must be critical, high or medium (got '$fail_on')" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."

auth=()
if [ -n "${GH_TOKEN:-}" ]; then
  auth=(-H "Authorization: Bearer $GH_TOKEN")
fi
latest_cli=$(curl -fsSL ${auth[@]+"${auth[@]}"} https://api.github.com/repos/earthly/lunar-dist/releases/latest \
  | jq -r '.tag_name // empty')
latest_cli="${latest_cli#v}"
if [ -z "$latest_cli" ]; then
  echo "could not resolve the latest lunar-dist release" >&2
  exit 1
fi

refs=$(scripts/pushed-image-refs.sh "$tag")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# One DB download up front instead of one per parallel scan.
grype db update >/dev/null

scan_one() {
  local ref="$1" name cli verdict gating crit high
  name="${ref#earthly/lunar-lib:}"
  local out="$work/$name"
  if ! docker pull -q "$ref" >/dev/null 2>"$out.err"; then
    printf '%s\t-\t-\t-\tFAIL: pull failed: %s\n' "$name" "$(tr '\n' ' ' < "$out.err")" > "$out.tsv"
    return 0
  fi
  cli=$(docker run --rm --entrypoint lunar "$ref" version 2>/dev/null | awk 'NR==1 {print $1}' || true)
  if ! grype "docker:$ref" --only-fixed -o json > "$out.json" 2>"$out.err"; then
    docker rmi -f "$ref" >/dev/null 2>&1 || true
    printf '%s\t%s\t-\t-\tFAIL: grype failed: %s\n' "$name" "${cli:-missing}" "$(tail -n 3 "$out.err" | tr '\n' ' ')" > "$out.tsv"
    return 0
  fi
  docker rmi -f "$ref" >/dev/null 2>&1 || true
  # --only-fixed moves every finding without a fix to .ignoredMatches.
  crit=$(jq '[.matches[] | select(.vulnerability.severity == "Critical")] | length' "$out.json")
  high=$(jq '[.matches[] | select(.vulnerability.severity == "High")] | length' "$out.json")
  gating=$(jq --arg s "$severities" \
    '[.matches[] | select(.vulnerability.severity as $v | $s | split(" ") | index($v))] | length' "$out.json")
  verdict="pass"
  if [ "$gating" -gt 0 ]; then
    verdict="FAIL: $gating fixable at $fail_on or above"
  fi
  if [ "$cli" != "$latest_cli" ]; then
    [ "$verdict" = "pass" ] && verdict="FAIL:" || verdict="$verdict;"
    verdict="$verdict lunar CLI ${cli:-missing}, latest is $latest_cli"
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$name" "${cli:-missing}" "$crit" "$high" "$verdict" > "$out.tsv"
}
export -f scan_one
export work severities fail_on latest_cli

# shellcheck disable=SC2016  # $1 belongs to the inner bash -c, not this shell
printf '%s\n' "$refs" | xargs -P "${SCAN_JOBS:-4}" -I{} bash -c 'scan_one "$1"' _ {}

expected=$(printf '%s\n' "$refs" | wc -l | tr -d ' ')
got=$(find "$work" -name '*.tsv' | wc -l | tr -d ' ')
results=$(cat "$work"/*.tsv 2>/dev/null | sort)
failed=$(printf '%s\n' "$results" | awk -F'\t' '$5 != "pass"' | grep -c . || true)
if [ "$got" -ne "$expected" ]; then
  failed=$((failed + expected - got))
fi

report() {
  echo "### CVE scan: \`$tag\` (grype, fail on fixable $fail_on+, lunar CLI $latest_cli)"
  echo
  echo "| image | lunar CLI | fixable crit | fixable high | result |"
  echo "|---|---|---|---|---|"
  printf '%s\n' "$results" | awk -F'\t' 'NF {printf "| %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5}'
  if [ "$got" -ne "$expected" ]; then
    echo
    echo "**$((expected - got)) of $expected images produced no result.**"
  fi
  for json in "$work"/*.json; do
    [ -e "$json" ] || continue
    local name findings
    name=$(basename "$json" .json)
    findings=$(jq -r --arg s "$severities" '[.matches[]
        | select(.vulnerability.severity as $v | $s | split(" ") | index($v))
        | "\(.vulnerability.severity) \(.vulnerability.id) \(.artifact.name)@\(.artifact.version) -> \((.vulnerability.fix.versions // []) | join(",")) (\([.artifact.locations[]?.path] | join(";")))"]
      | unique | .[]' "$json")
    if [ -n "$findings" ]; then
      echo
      echo "<details><summary>$name: $(printf '%s\n' "$findings" | wc -l | tr -d ' ') gating findings</summary>"
      echo
      echo '```'
      printf '%s\n' "$findings"
      echo '```'
      echo "</details>"
    fi
  done
}

report
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  report >> "$GITHUB_STEP_SUMMARY"
fi

if [ "$failed" -gt 0 ]; then
  echo >&2
  echo "$failed of $expected images failed the scan" >&2
  exit 1
fi
echo >&2
echo "All $expected images passed." >&2
