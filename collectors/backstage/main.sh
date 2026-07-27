#!/bin/bash

set -e

SCRIPT_DIR="$(dirname "$0")"

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_PATHS"

CATALOG_FILE=""
for candidate in "${CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    CATALOG_FILE="./$candidate"
    break
  fi
done

if [ -z "$CATALOG_FILE" ]; then
  # No catalog-info.yaml found — write nothing. Absence of `.catalog.native.backstage`
  # IS the signal. Policies use Check.exists(".catalog.native.backstage") to detect.
  exit 0
fi

PATH_NORMALIZED="${CATALOG_FILE#./}"

YQ_ERR=$(mktemp)
trap 'rm -f "$YQ_ERR"' EXIT

PARSE_OK=false
if PARSED_JSON=$(yq -o=json '.' "$CATALOG_FILE" 2>"$YQ_ERR"); then
  RESULT=$(echo "$PARSED_JSON" | python3 "$SCRIPT_DIR/lint_backstage.py" --path "$PATH_NORMALIZED")
  PARSE_OK=true
else
  ERR_MSG=$(tr '\n' ' ' < "$YQ_ERR" | sed 's/[[:space:]]*$//' | head -c 500)
  [ -z "$ERR_MSG" ] && ERR_MSG="YAML parse error"
  RESULT=$(jq -n \
    --arg path "$PATH_NORMALIZED" \
    --arg msg "$ERR_MSG" \
    '{
      valid: false,
      errors: [{line: 0, message: $msg, severity: "error"}],
      path: $path
    }')
fi

# --- Referential integrity (optional) ---
# When backstage_url is configured, cross-check the declared grouping references
# (spec.domain, spec.system) against the live Backstage catalog and record the
# outcome under .refs. `.refs.checked = true` is always written when configured,
# so the policy can distinguish "configured" from "not configured"; a transient
# failure is recorded as {name, error} (rather than omitted) so an outage stays
# distinguishable from a real miss. When backstage_url is unset, nothing is
# written and behavior is identical to a plain parse-and-lint run.
BACKSTAGE_URL="${LUNAR_VAR_BACKSTAGE_URL:-}"
if [ "$PARSE_OK" = true ] && [ -n "$BACKSTAGE_URL" ]; then
  BASE_URL="${BACKSTAGE_URL%/}"
  DEFAULT_NS=$(echo "$PARSED_JSON" | jq -r '.metadata.namespace // "default"')

  resolve_ref() {
    # $1 = Backstage kind (domain|system); $2 = declared reference value.
    # Emits a JSON object: {name, exists} on a definitive 200/404, or
    # {name, error} on a transient failure (connection error / 5xx).
    local kind="$1" value="$2" ref ns name http_code curl_status
    # Strip an explicit "kind:" prefix, then split an optional "namespace/"
    # prefix; a bare value uses the component's namespace (falling back to
    # "default"). Mirrors Backstage's own reference resolution.
    ref="${value#*:}"
    if [[ "$ref" == */* ]]; then
      ns="${ref%%/*}"
      name="${ref#*/}"
    else
      ns="$DEFAULT_NS"
      name="$ref"
    fi

    local auth=()
    [ -n "${LUNAR_SECRET_BACKSTAGE_TOKEN:-}" ] && auth=(-H "Authorization: Bearer ${LUNAR_SECRET_BACKSTAGE_TOKEN}")

    set +e
    http_code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
      "${auth[@]}" \
      "${BASE_URL}/api/catalog/entities/by-name/${kind}/${ns}/${name}")
    curl_status=$?
    set -e

    if [ "$curl_status" -ne 0 ]; then
      jq -n --arg name "$value" --arg err "request failed (curl exit ${curl_status})" \
        '{name: $name, error: $err}'
    elif [ "$http_code" = "200" ]; then
      jq -n --arg name "$value" '{name: $name, exists: true}'
    elif [ "$http_code" = "404" ]; then
      jq -n --arg name "$value" '{name: $name, exists: false}'
    else
      jq -n --arg name "$value" --arg err "HTTP ${http_code}" '{name: $name, error: $err}'
    fi
  }

  REFS='{"checked":true}'

  DOMAIN_REF=$(echo "$PARSED_JSON" | jq -r '.spec.domain // empty')
  if [ -n "$DOMAIN_REF" ]; then
    DOMAIN_ENTRY=$(resolve_ref domain "$DOMAIN_REF")
    REFS=$(echo "$REFS" | jq --argjson d "$DOMAIN_ENTRY" '. + {domain: $d}')
  fi

  SYSTEM_REF=$(echo "$PARSED_JSON" | jq -r '.spec.system // empty')
  if [ -n "$SYSTEM_REF" ]; then
    SYSTEM_ENTRY=$(resolve_ref system "$SYSTEM_REF")
    REFS=$(echo "$REFS" | jq --argjson s "$SYSTEM_ENTRY" '. + {system: $s}')
  fi

  RESULT=$(echo "$RESULT" | jq --argjson refs "$REFS" '. + {refs: $refs}')
fi

echo "$RESULT" | lunar collect -j ".catalog.native.backstage" -
