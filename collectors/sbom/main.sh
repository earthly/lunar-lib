#!/bin/bash
set -e

echo "Running sbom collector" >&2

# If syft is not available, fail fast so the job log makes it obvious.
if ! command -v syft >/dev/null 2>&1; then
  echo "syft not found in PATH; run the sbom collector's install.sh first." >&2
  exit 1
fi

# Enable richer license detection in syft via remote lookups.
# Go: rely on remote module metadata; assume no useful local module cache in CI images.
export SYFT_GOLANG_SEARCH_LOCAL_MOD_CACHE_LICENSES="${SYFT_GOLANG_SEARCH_LOCAL_MOD_CACHE_LICENSES:-false}"
export SYFT_GOLANG_SEARCH_REMOTE_LICENSES="${SYFT_GOLANG_SEARCH_REMOTE_LICENSES:-true}"

# Java: allow syft to use network (e.g., Maven repos) for additional metadata, including licenses.
export SYFT_JAVA_USE_NETWORK="${SYFT_JAVA_USE_NETWORK:-true}"

# Node.js / JavaScript: enable remote license lookups when local metadata is incomplete.
export SYFT_JAVASCRIPT_SEARCH_REMOTE_LICENSES="${SYFT_JAVASCRIPT_SEARCH_REMOTE_LICENSES:-true}"

# For Python projects: install dependencies to a target directory (without venv) for license detection.
# This allows syft to read license metadata from installed packages.
python_packages_dir=""
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  PYTHON_CMD=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
  
  # Check for Python dependency files
  if [[ -f "requirements.txt" ]] || [[ -f "pyproject.toml" ]] || [[ -f "Pipfile" ]] || [[ -f "setup.py" ]]; then
    python_packages_dir=".python-packages-sbom"
    echo "Detected Python project; installing packages to directory for license detection..." >&2
    
    # Install packages to target directory (no venv needed)
    if [[ -f "requirements.txt" ]]; then
      echo "Installing dependencies from requirements.txt..." >&2
      "$PYTHON_CMD" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
      "$PYTHON_CMD" -m pip install --quiet --target "$python_packages_dir" -r requirements.txt >/dev/null 2>&1 || \
        echo "Warning: Some Python packages failed to install; license detection may be incomplete" >&2
    elif [[ -f "pyproject.toml" ]]; then
      echo "Installing dependencies from pyproject.toml..." >&2
      "$PYTHON_CMD" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
      "$PYTHON_CMD" -m pip install --quiet --target "$python_packages_dir" . >/dev/null 2>&1 || \
        echo "Warning: Installation from pyproject.toml failed; license detection may be incomplete" >&2
    fi
  fi
fi

# Generate a CycloneDX JSON SBOM for the current repository.
# This works even for "config-only" repos; the SBOM will just have no components.
tmp_sbom="$(mktemp)"

if ! syft dir:. -o cyclonedx-json > "$tmp_sbom"; then
  echo "syft failed to generate SBOM" >&2
  rm -f "$tmp_sbom"
  exit 1
fi

# Optionally skip collecting completely empty SBOMs.
if jq -e '(.components // []) | length == 0' "$tmp_sbom" >/dev/null 2>&1; then
  echo "SBOM has no components; skipping collection" >&2
  rm -f "$tmp_sbom"
  exit 0
fi

# Submit the SBOM as component JSON under .sbom.cyclonedx.
cat "$tmp_sbom" | lunar collect -j ".sbom.cyclonedx" -

# Cleanup
rm -f "$tmp_sbom"
if [[ -n "$python_packages_dir" ]] && [[ -d "$python_packages_dir" ]]; then
  rm -rf "$python_packages_dir"
  echo "Cleaned up temporary Python packages directory" >&2
fi

