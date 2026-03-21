#!/bin/bash
set -e

echo "Running syft generate collector" >&2

# Record source metadata
SYFT_VERSION=$(syft version -o json 2>/dev/null | jq -r '.version // empty' || syft version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
lunar collect ".sbom.auto.source.tool" "syft"
lunar collect ".sbom.auto.source.integration" "code"
if [ -n "$SYFT_VERSION" ]; then
  lunar collect ".sbom.auto.source.version" "$SYFT_VERSION"
fi

# Enable richer license detection via remote lookups
export SYFT_GOLANG_SEARCH_LOCAL_MOD_CACHE_LICENSES="${SYFT_GOLANG_SEARCH_LOCAL_MOD_CACHE_LICENSES:-false}"
export SYFT_GOLANG_SEARCH_REMOTE_LICENSES="${SYFT_GOLANG_SEARCH_REMOTE_LICENSES:-true}"
export SYFT_JAVA_USE_NETWORK="${SYFT_JAVA_USE_NETWORK:-true}"
export SYFT_JAVASCRIPT_SEARCH_REMOTE_LICENSES="${SYFT_JAVASCRIPT_SEARCH_REMOTE_LICENSES:-true}"

# For Python projects: install deps to temp dir for license metadata detection
# (No cleanup needed — code collectors run in a disposable container)
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

# For Rust projects: fetch crate sources so we can extract license metadata
# Syft's Rust cataloger reads Cargo.lock for deps but doesn't resolve licenses,
# so we build a license map from the downloaded crate Cargo.toml files and inject
# it into the SBOM as a post-processing step.
RUST_LICENSE_MAP="/tmp/rust-license-map.json"
if command -v cargo >/dev/null 2>&1; then
  if [[ -f "Cargo.lock" ]] || [[ -f "Cargo.toml" ]]; then
    echo "Detected Rust project; fetching crate sources for license detection..." >&2
    cargo fetch --quiet 2>/dev/null || \
      echo "Warning: cargo fetch failed; license detection may be incomplete" >&2

    CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
    REGISTRY_SRC="$CARGO_HOME/registry/src"
    if [[ -d "$REGISTRY_SRC" ]]; then
      python3 -c "
import os, json, re, glob
registry = '$REGISTRY_SRC'
license_map = {}
for toml_path in glob.glob(os.path.join(registry, '*', '*', 'Cargo.toml')):
    crate_dir = os.path.basename(os.path.dirname(toml_path))
    m = re.match(r'^(.+)-(\d+\..*)$', crate_dir)
    if not m:
        continue
    crate_name, crate_version = m.group(1), m.group(2)
    with open(toml_path) as f:
        for line in f:
            lm = re.match(r'^license\s*=\s*[\"'"'"']([^\"'"'"']+)[\"'"'"']', line)
            if lm:
                lic = lm.group(1).strip().replace('/', ' OR ')
                license_map[crate_name + '@' + crate_version] = lic
                break
json.dump(license_map, open('$RUST_LICENSE_MAP', 'w'))
print(f'Built license map for {len(license_map)} Rust crates', flush=True)
" >&2 || echo "Warning: license map extraction failed" >&2
    fi
  fi
fi

# Generate CycloneDX JSON SBOM
SBOM_FILE="/tmp/sbom.json"
if ! syft dir:. -o cyclonedx-json > "$SBOM_FILE"; then
  echo "syft failed to generate SBOM" >&2
  exit 1
fi

# Skip empty SBOMs
if jq -e '(.components // []) | length == 0' "$SBOM_FILE" >/dev/null 2>&1; then
  echo "SBOM has no components; skipping collection" >&2
  exit 0
fi

# Inject Rust license data into SBOM components that are missing licenses
if [[ -f "$RUST_LICENSE_MAP" ]] && jq -e 'length > 0' "$RUST_LICENSE_MAP" >/dev/null 2>&1; then
  SBOM_INJECTED="/tmp/sbom-injected.json"
  jq --slurpfile lm "$RUST_LICENSE_MAP" '
    ($lm[0]) as $licenses |
    .components |= [.[] | if (.licenses == null or .licenses == []) then
      (.name + "@" + (.version // "")) as $key |
      if $licenses[$key] then
        ($licenses[$key]) as $lic |
        if ($lic | test(" OR | AND ")) then
          .licenses = [{ "expression": $lic }]
        else
          .licenses = [{ "license": { "id": $lic } }]
        end
      else . end
    else . end]
  ' "$SBOM_FILE" > "$SBOM_INJECTED" && mv "$SBOM_INJECTED" "$SBOM_FILE"
  count=$(jq '[.components[] | select(.licenses != null and .licenses != [])] | length' "$SBOM_FILE")
  echo "Injected licenses into SBOM ($count components with licenses)" >&2
fi

# Collect the full SBOM
cat "$SBOM_FILE" | lunar collect -j ".sbom.auto.cyclonedx" -
