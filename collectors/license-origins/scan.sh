#!/bin/bash
set -e

SCRIPT_DIR="$(dirname "$0")"
COLLECTOR_VERSION="0.1.0"

echo "Running license-origins scan collector v${COLLECTOR_VERSION}" >&2

source "$SCRIPT_DIR/countries.sh"

# --- Configuration from inputs ---
CACHE_ENABLED="${LUNAR_VAR_CACHE_ENABLED:-true}"
DB_HOST="${LUNAR_VAR_CACHE_DB_HOST:-postgres}"
DB_PORT="${LUNAR_VAR_CACHE_DB_PORT:-5432}"
DB_NAME="${LUNAR_VAR_CACHE_DB_NAME:-hub}"
DB_USER="${LUNAR_VAR_CACHE_DB_USER:-lunar}"
DB_PASSWORD="${LUNAR_SECRET_CACHE_DB_PASSWORD:-}"

CACHE_TABLE="license_origin_cache"

if [ "$CACHE_ENABLED" = "true" ] && [ -z "$DB_PASSWORD" ]; then
  echo "No CACHE_DB_PASSWORD secret provided; running without cache" >&2
  CACHE_ENABLED="false"
fi

# --- Postgres helpers ---

psql_cmd() {
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --no-psqlrc -qtAX "$@" 2>/dev/null
}

init_cache_table() {
  psql_cmd -c "
    CREATE TABLE IF NOT EXISTS ${CACHE_TABLE} (
      purl        TEXT PRIMARY KEY,
      countries   TEXT[],
      excerpts    JSONB,
      source      TEXT DEFAULT 'local',
      scanned_at  TIMESTAMPTZ DEFAULT NOW()
    );
  " || {
    echo "Warning: Failed to create cache table; continuing without cache" >&2
    CACHE_ENABLED="false"
  }
}

cache_lookup() {
  local purl="$1"
  psql_cmd -c "
    SELECT json_build_object(
      'countries', COALESCE(array_to_json(countries), '[]'::json),
      'excerpts',  COALESCE(excerpts, '[]'::jsonb)
    )
    FROM ${CACHE_TABLE}
    WHERE purl = '$(echo "$purl" | sed "s/'/''/g")'
    LIMIT 1;
  "
}

cache_store() {
  local purl="$1"
  local countries_pg="$2"     # Postgres array literal: {Germany,Netherlands}
  local excerpts_json="$3"    # JSON array
  local escaped_purl
  escaped_purl="$(echo "$purl" | sed "s/'/''/g")"

  psql_cmd -c "
    INSERT INTO ${CACHE_TABLE} (purl, countries, excerpts, source)
    VALUES (
      '${escaped_purl}',
      '${countries_pg}',
      '${excerpts_json}'::jsonb,
      'local'
    )
    ON CONFLICT (purl) DO NOTHING;
  "
}

# --- SBOM helpers ---

get_sbom_purls() {
  local sbom_file="$1"
  jq -r '.components[]? | select(.purl != null) | .purl' "$sbom_file" 2>/dev/null || true
}

purl_to_name() {
  local purl="$1"
  echo "$purl" | sed -E 's|^pkg:[^/]+/([^@]+).*|\1|; s|.*/||'
}

# --- License file scanning ---

find_license_files() {
  find . -maxdepth 5 \
    \( -iname "LICENSE" -o -iname "LICENSE.*" -o -iname "LICENCE" -o -iname "LICENCE.*" \
       -o -iname "COPYING" -o -iname "COPYING.*" -o -iname "NOTICE" -o -iname "NOTICE.*" \) \
    -not -path "./.git/*" \
    -type f 2>/dev/null || true
}

find_license_for_package() {
  local pkg_name="$1"
  local found=""

  for search_dir in "node_modules/${pkg_name}" "vendor" ".python-packages" "target" ".gradle"; do
    if [ -d "$search_dir" ]; then
      found=$(find "$search_dir" -maxdepth 3 \
        \( -iname "LICENSE" -o -iname "LICENSE.*" -o -iname "LICENCE" -o -iname "LICENCE.*" \
           -o -iname "COPYING" -o -iname "COPYING.*" -o -iname "NOTICE" -o -iname "NOTICE.*" \) \
        -type f 2>/dev/null | head -1)
      if [ -n "$found" ]; then
        echo "$found"
        return 0
      fi
    fi
  done

  find . -maxdepth 4 -path "*${pkg_name}*" \
    \( -iname "LICENSE" -o -iname "LICENSE.*" -o -iname "LICENCE" -o -iname "LICENCE.*" \
       -o -iname "COPYING" -o -iname "COPYING.*" -o -iname "NOTICE" -o -iname "NOTICE.*" \) \
    -not -path "./.git/*" \
    -type f 2>/dev/null | head -1
}

scan_file_for_countries() {
  local file="$1"
  local found_countries=()
  local found_excerpts=()

  if [ ! -f "$file" ] || [ ! -r "$file" ]; then
    return
  fi

  local content
  content=$(cat "$file" 2>/dev/null || true)
  [ -z "$content" ] && return

  for country in "${COUNTRY_NAMES[@]}"; do
    local matching_line
    matching_line=$(echo "$content" | grep -i -m 1 -F "$country" 2>/dev/null || true)
    if [ -n "$matching_line" ]; then
      local already_found=false
      for c in "${found_countries[@]}"; do
        if [ "$c" = "$country" ]; then
          already_found=true
          break
        fi
      done
      if [ "$already_found" = false ]; then
        found_countries+=("$country")
        local trimmed
        trimmed=$(echo "$matching_line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | head -c 200)
        found_excerpts+=("$trimmed")
      fi
    fi
  done

  if [ ${#found_countries[@]} -gt 0 ]; then
    local countries_json
    countries_json=$(printf '%s\n' "${found_countries[@]}" | jq -R . | jq -s -c .)
    local excerpts_json
    excerpts_json=$(printf '%s\n' "${found_excerpts[@]}" | jq -R . | jq -s -c .)
    printf '%s\n%s\n' "$countries_json" "$excerpts_json"
  fi
}

# --- Main ---

# Step 1: Source metadata
lunar collect ".sbom.license_origins.source.tool" "license-origins"
lunar collect ".sbom.license_origins.source.integration" "code"
lunar collect ".sbom.license_origins.source.version" "$COLLECTOR_VERSION"

# Step 2: Generate SBOM with syft and write to .sbom.auto (replaces syft collector)
SBOM_FILE="/tmp/license-origins-sbom.json"

SYFT_VERSION=$(syft version -o json 2>/dev/null | jq -r '.version // empty' || syft version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
lunar collect ".sbom.auto.source.tool" "syft"
lunar collect ".sbom.auto.source.integration" "code"
if [ -n "$SYFT_VERSION" ]; then
  lunar collect ".sbom.auto.source.version" "$SYFT_VERSION"
fi

export SYFT_GOLANG_SEARCH_LOCAL_MOD_CACHE_LICENSES="${SYFT_GOLANG_SEARCH_LOCAL_MOD_CACHE_LICENSES:-false}"
export SYFT_GOLANG_SEARCH_REMOTE_LICENSES="${SYFT_GOLANG_SEARCH_REMOTE_LICENSES:-true}"
export SYFT_JAVA_USE_NETWORK="${SYFT_JAVA_USE_NETWORK:-true}"
export SYFT_JAVASCRIPT_SEARCH_REMOTE_LICENSES="${SYFT_JAVASCRIPT_SEARCH_REMOTE_LICENSES:-true}"

python_packages_dir=""
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  PYTHON_CMD=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
  if [[ -f "requirements.txt" ]] || [[ -f "pyproject.toml" ]] || [[ -f "Pipfile" ]] || [[ -f "setup.py" ]]; then
    python_packages_dir=".python-packages-sbom"
    echo "Detected Python project; installing packages for license detection..." >&2
    if [[ -f "requirements.txt" ]]; then
      "$PYTHON_CMD" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
      "$PYTHON_CMD" -m pip install --quiet --target "$python_packages_dir" -r requirements.txt >/dev/null 2>&1 || \
        echo "Warning: Some Python packages failed to install; license detection may be incomplete" >&2
    elif [[ -f "pyproject.toml" ]]; then
      "$PYTHON_CMD" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
      "$PYTHON_CMD" -m pip install --quiet --target "$python_packages_dir" . >/dev/null 2>&1 || \
        echo "Warning: Installation from pyproject.toml failed; license detection may be incomplete" >&2
    fi
  fi
fi

# Install Node.js dependencies so license files are on disk for scanning
if [[ -f "package-lock.json" ]] || [[ -f "yarn.lock" ]] || [[ -f "pnpm-lock.yaml" ]]; then
  if command -v npm >/dev/null 2>&1; then
    echo "Detected Node.js project; installing packages for license scanning..." >&2
    npm install --ignore-scripts --no-audit --no-fund >/dev/null 2>&1 || \
      echo "Warning: npm install failed; license file scanning may be incomplete" >&2
  fi
fi

echo "Generating SBOM with syft..." >&2
if ! syft dir:. -o cyclonedx-json > "$SBOM_FILE" 2>/dev/null; then
  echo "syft failed to generate SBOM" >&2
  exit 1
fi

if jq -e '(.components // []) | length == 0' "$SBOM_FILE" >/dev/null 2>&1; then
  echo "No dependencies found; skipping license origin scan" >&2
  exit 0
fi

echo "SBOM generated: $(jq '.components | length' "$SBOM_FILE") components" >&2

cat "$SBOM_FILE" | lunar collect -j ".sbom.auto.cyclonedx" -

# Step 3: Initialize cache
if [ "$CACHE_ENABLED" = "true" ]; then
  echo "Initializing cache table..." >&2
  init_cache_table
fi

# Step 4: Scan each dependency
PURLS=$(get_sbom_purls "$SBOM_FILE")
PURL_COUNT=$(echo "$PURLS" | grep -c . || true)

echo "Scanning ${PURL_COUNT} dependencies for license origin signals..." >&2

PACKAGES_JSON="[]"
FILES_SCANNED=0
PACKAGES_WITH_MENTIONS=0
ALL_COUNTRIES_FOUND="[]"
CACHE_HITS=0
CACHE_MISSES=0

while IFS= read -r purl; do
  [ -z "$purl" ] && continue

  pkg_name=$(purl_to_name "$purl")

  # Try cache first
  if [ "$CACHE_ENABLED" = "true" ]; then
    cached_result=$(cache_lookup "$purl")
    if [ -n "$cached_result" ]; then
      CACHE_HITS=$((CACHE_HITS + 1))

      cached_countries=$(echo "$cached_result" | jq -r '.countries')
      cached_excerpts=$(echo "$cached_result" | jq -r '.excerpts')
      country_count=$(echo "$cached_countries" | jq 'length')

      if [ "$country_count" -gt 0 ]; then
        PACKAGES_WITH_MENTIONS=$((PACKAGES_WITH_MENTIONS + 1))

        pkg_entry=$(jq -n \
          --arg purl "$purl" \
          --arg name "$pkg_name" \
          --arg license_file "(cached)" \
          --argjson countries "$cached_countries" \
          --argjson excerpts "$cached_excerpts" \
          '{
            purl: $purl,
            name: $name,
            license_file: $license_file,
            countries: $countries,
            excerpts: $excerpts,
            cached: true
          }')
        PACKAGES_JSON=$(echo "$PACKAGES_JSON" | jq --argjson entry "$pkg_entry" '. + [$entry]')
        ALL_COUNTRIES_FOUND=$(jq -n --argjson existing "$ALL_COUNTRIES_FOUND" --argjson new "$cached_countries" '$existing + $new | unique')
      fi
      continue
    fi
  fi

  CACHE_MISSES=$((CACHE_MISSES + 1))

  # Find license file for this package
  license_file=$(find_license_for_package "$pkg_name")
  if [ -z "$license_file" ]; then
    # Store empty result in cache so we don't re-scan
    if [ "$CACHE_ENABLED" = "true" ]; then
      cache_store "$purl" "{}" "[]"
    fi
    continue
  fi

  FILES_SCANNED=$((FILES_SCANNED + 1))

  # Scan the file
  scan_result=$(scan_file_for_countries "$license_file")
  if [ -n "$scan_result" ]; then
    countries_json=$(echo "$scan_result" | head -1)
    excerpts_json=$(echo "$scan_result" | tail -1)

    PACKAGES_WITH_MENTIONS=$((PACKAGES_WITH_MENTIONS + 1))

    pkg_entry=$(jq -n \
      --arg purl "$purl" \
      --arg name "$pkg_name" \
      --arg license_file "$license_file" \
      --argjson countries "$countries_json" \
      --argjson excerpts "$excerpts_json" \
      '{
        purl: $purl,
        name: $name,
        license_file: $license_file,
        countries: $countries,
        excerpts: $excerpts,
        cached: false
      }')
    PACKAGES_JSON=$(echo "$PACKAGES_JSON" | jq --argjson entry "$pkg_entry" '. + [$entry]')
    ALL_COUNTRIES_FOUND=$(jq -n --argjson existing "$ALL_COUNTRIES_FOUND" --argjson new "$countries_json" '$existing + $new | unique')

    # Store in cache
    if [ "$CACHE_ENABLED" = "true" ]; then
      pg_countries=$(echo "$countries_json" | jq -r 'join(",")')
      cache_store "$purl" "{${pg_countries}}" "$excerpts_json"
    fi
  else
    # No countries found — cache the empty result
    if [ "$CACHE_ENABLED" = "true" ]; then
      cache_store "$purl" "{}" "[]"
    fi
  fi

done <<< "$PURLS"

# Step 5: Write results to Component JSON
RESULT=$(jq -n \
  --argjson packages "$PACKAGES_JSON" \
  --argjson countries_found "$ALL_COUNTRIES_FOUND" \
  --arg files_scanned "$FILES_SCANNED" \
  --arg packages_with_mentions "$PACKAGES_WITH_MENTIONS" \
  --arg cache_hits "$CACHE_HITS" \
  --arg cache_misses "$CACHE_MISSES" \
  '{
    packages: $packages,
    summary: {
      files_scanned: ($files_scanned | tonumber),
      packages_with_mentions: ($packages_with_mentions | tonumber),
      countries_found: $countries_found,
      cache_hits: ($cache_hits | tonumber),
      cache_misses: ($cache_misses | tonumber)
    }
  }')

echo "$RESULT" | lunar collect -j ".sbom.license_origins" -

echo "License origin scan complete: ${PACKAGES_WITH_MENTIONS} packages with country mentions, ${CACHE_HITS} cache hits, ${CACHE_MISSES} cache misses" >&2
