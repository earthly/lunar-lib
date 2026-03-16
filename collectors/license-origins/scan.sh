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
  local countries_pg="$2"
  local excerpts_json="$3"
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

# --- Per-language dependency fetching ---

LICENSE_SEARCH_DIRS=()

fetch_rust_deps() {
  if [[ ! -f "Cargo.toml" ]]; then
    return
  fi
  if ! command -v cargo >/dev/null 2>&1; then
    echo "Rust project detected but cargo not available; skipping Rust license scan" >&2
    return
  fi
  if [[ ! -f "Cargo.lock" ]]; then
    echo "No Cargo.lock found; generating lockfile..." >&2
    if ! cargo generate-lockfile 2>&1; then
      echo "Warning: cargo generate-lockfile failed; Rust license scanning may be incomplete" >&2
      return
    fi
  fi
  echo "Fetching Rust dependencies (cargo fetch)..." >&2
  if ! cargo fetch 2>&1; then
    echo "Warning: cargo fetch failed; Rust license scanning may be incomplete" >&2
    return
  fi
  local cargo_home="${CARGO_HOME:-$HOME/.cargo}"
  local diag_registry_ls=$(ls "$cargo_home/registry/" 2>&1 || echo "NOT_FOUND")
  local diag_src_ls=$(ls "$cargo_home/registry/src/" 2>&1 || echo "NOT_FOUND")
  local diag_lic_count=0
  if [ -d "$cargo_home/registry/src" ]; then
    LICENSE_SEARCH_DIRS+=("$cargo_home/registry/src")
    diag_lic_count=$(find "$cargo_home/registry/src" -maxdepth 6 -iname "LICENSE*" -type f 2>/dev/null | wc -l)
    echo "Rust deps: $diag_lic_count license files in $cargo_home/registry/src" >&2
  else
    echo "Warning: $cargo_home/registry/src does not exist after cargo fetch" >&2
  fi
  lunar collect ".sbom.license_origins._debug_rust.cargo_home" "$cargo_home"
  lunar collect ".sbom.license_origins._debug_rust.registry_ls" "$diag_registry_ls"
  lunar collect ".sbom.license_origins._debug_rust.src_ls" "$diag_src_ls"
  lunar collect ".sbom.license_origins._debug_rust.license_file_count" "$diag_lic_count"
}

fetch_go_deps() {
  if [[ ! -f "go.mod" ]]; then
    return
  fi
  if ! command -v go >/dev/null 2>&1; then
    echo "Go project detected but go not available; skipping Go license scan" >&2
    return
  fi
  echo "Fetching Go dependencies (go mod download)..." >&2
  go mod download 2>/dev/null || {
    echo "Warning: go mod download failed; Go license scanning may be incomplete" >&2
    return
  }
  local gopath="${GOPATH:-$HOME/go}"
  if [ -d "$gopath/pkg/mod" ]; then
    LICENSE_SEARCH_DIRS+=("$gopath/pkg/mod")
    echo "Go deps fetched to $gopath/pkg/mod" >&2
  fi
}

fetch_node_deps() {
  if [[ ! -f "package-lock.json" ]] && [[ ! -f "yarn.lock" ]] && [[ ! -f "pnpm-lock.yaml" ]]; then
    return
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "Node.js project detected but npm not available; skipping Node license scan" >&2
    return
  fi
  echo "Fetching Node.js dependencies (npm install)..." >&2
  npm install --ignore-scripts --no-audit --no-fund --no-optional >/dev/null 2>&1 || {
    echo "Warning: npm install failed; Node license scanning may be incomplete" >&2
    return
  }
  if [ -d "node_modules" ]; then
    LICENSE_SEARCH_DIRS+=("node_modules")
    echo "Node deps installed to node_modules/" >&2
  fi
}

fetch_python_deps() {
  if [[ ! -f "requirements.txt" ]] && [[ ! -f "pyproject.toml" ]] && [[ ! -f "Pipfile" ]] && [[ ! -f "setup.py" ]]; then
    return
  fi
  local python_cmd=""
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  else
    echo "Python project detected but python not available; skipping Python license scan" >&2
    return
  fi

  local target_dir=".python-packages-scan"
  echo "Fetching Python dependencies (pip install)..." >&2
  "$python_cmd" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true

  if [[ -f "requirements.txt" ]]; then
    "$python_cmd" -m pip install --quiet --target "$target_dir" -r requirements.txt >/dev/null 2>&1 || {
      echo "Warning: pip install failed; Python license scanning may be incomplete" >&2
      return
    }
  elif [[ -f "pyproject.toml" ]]; then
    "$python_cmd" -m pip install --quiet --target "$target_dir" . >/dev/null 2>&1 || {
      echo "Warning: pip install from pyproject.toml failed; Python license scanning may be incomplete" >&2
      return
    }
  fi

  if [ -d "$target_dir" ]; then
    LICENSE_SEARCH_DIRS+=("$target_dir")
    echo "Python deps installed to $target_dir/" >&2
  fi
}

# --- License file scanning ---

find_license_for_package() {
  local pkg_name="$1"

  for search_dir in "${LICENSE_SEARCH_DIRS[@]}"; do
    [ -d "$search_dir" ] || continue
    local found
    found=$(find "$search_dir" -maxdepth 6 -path "*${pkg_name}*" \
      \( -iname "LICENSE" -o -iname "LICENSE.*" -o -iname "LICENCE" -o -iname "LICENCE.*" \
         -o -iname "COPYING" -o -iname "COPYING.*" -o -iname "NOTICE" -o -iname "NOTICE.*" \) \
      -type f 2>/dev/null | head -1)
    if [ -n "$found" ]; then
      echo "$found"
      return 0
    fi
  done

  # Fallback: search repo root for any matching license files
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
    # Use word-boundary matching to avoid substrings (e.g. "Oman" in "Roman")
    local pattern
    pattern=$(echo "$country" | sed 's/[.[\*^$()+?{|]/\\&/g')
    matching_line=$(echo "$content" | grep -i -m 1 -w "$pattern" 2>/dev/null || true)
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

export SYFT_GOLANG_SEARCH_LOCAL_MOD_CACHE_LICENSES="${SYFT_GOLANG_SEARCH_LOCAL_MOD_CACHE_LICENSES:-true}"
export SYFT_GOLANG_SEARCH_REMOTE_LICENSES="${SYFT_GOLANG_SEARCH_REMOTE_LICENSES:-true}"
export SYFT_JAVA_USE_NETWORK="${SYFT_JAVA_USE_NETWORK:-true}"
export SYFT_JAVASCRIPT_SEARCH_REMOTE_LICENSES="${SYFT_JAVASCRIPT_SEARCH_REMOTE_LICENSES:-true}"

# Step 3: Fetch dependencies per language so license files are on disk
echo "Detecting project languages and fetching dependencies..." >&2
fetch_rust_deps
fetch_go_deps
fetch_node_deps
fetch_python_deps
echo "License search directories: ${LICENSE_SEARCH_DIRS[*]:-"(repo root only)"}" >&2

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

# Step 4: Initialize cache
if [ "$CACHE_ENABLED" = "true" ]; then
  echo "Initializing cache table..." >&2
  init_cache_table
fi

# Step 5: Scan each dependency
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

    if [ "$CACHE_ENABLED" = "true" ]; then
      pg_countries=$(echo "$countries_json" | jq -r 'join(",")')
      cache_store "$purl" "{${pg_countries}}" "$excerpts_json"
    fi
  else
    if [ "$CACHE_ENABLED" = "true" ]; then
      cache_store "$purl" "{}" "[]"
    fi
  fi

done <<< "$PURLS"

# Step 6: Write results to Component JSON
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

echo "License origin scan complete: ${PACKAGES_WITH_MENTIONS} packages with country mentions, ${FILES_SCANNED} files scanned, ${CACHE_HITS} cache hits, ${CACHE_MISSES} cache misses" >&2
