#!/bin/bash
set -e

echo "Running syft generate collector" >&2

if ! command -v syft >/dev/null 2>&1; then
  echo "syft not found in PATH; run the syft collector's install.sh first." >&2
  exit 1
fi

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

# Generate CycloneDX JSON SBOM
tmp_sbom="$(mktemp)"
if ! syft dir:. -o cyclonedx-json > "$tmp_sbom"; then
  echo "syft failed to generate SBOM" >&2
  exit 1
fi

# Skip empty SBOMs
if jq -e '(.components // []) | length == 0' "$tmp_sbom" >/dev/null 2>&1; then
  echo "SBOM has no components; skipping collection" >&2
  exit 0
fi

# Collect the full SBOM
cat "$tmp_sbom" | lunar collect -j ".sbom.auto.cyclonedx" -
