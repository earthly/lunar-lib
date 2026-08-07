#!/bin/bash
#
# Backstage catalog-info Cataloger — COMMIT-TRIGGERED variant (component-repo).
#
# Runs once per affected component whenever its repo receives a commit, with
# the component's repo checked out as the working directory. Reads
# `catalog-info.yaml` (or `.yml`) straight from the checkout — no GitHub
# Contents API call and no `GH_TOKEN` — then hands the file to the shared
# augment pipeline in `helpers.sh`, which parses it, picks the matching
# `Component` entity, and writes a single `.components["$LUNAR_COMPONENT_ID"]`
# entry (plus a `.domains` stub) into the Catalog JSON.
#
# The scheduled sibling `main.sh` shares the same pipeline — only the
# acquisition step (its GitHub fetch vs. this file's checkout read) differs.
# Keep augmentation logic in `helpers.sh`, not here.
#
# Silent skips (exit 0 with a log line, no write):
#   - No catalog-info.yaml at any of the configured paths in the checkout
#   - YAML parse error / no matching Component (handled in helpers.sh)
#
# Inputs (LUNAR_VAR_*):
#   paths                    (default catalog-info.yaml,catalog-info.yml)
#   ...matcher/transform inputs are read in helpers.sh
#   (note: `branch` does not apply here — the hook checks out the ref)
#
# Secrets: none — the file comes from the checkout, not the API.

set -euo pipefail

COMPONENT_ID="${LUNAR_COMPONENT_ID:?LUNAR_COMPONENT_ID must be set by the component-repo runner}"

PATHS="${LUNAR_VAR_PATHS:-catalog-info.yaml,catalog-info.yml}"

echo "Component: $COMPONENT_ID"
echo "Paths: $PATHS"

# --- Read catalog-info.yaml from the checkout -----------------------------
# The component-repo hook runs with the component's repo as the working
# directory (same contract as a `code`-hook collector), so try each configured
# path relative to CWD. First match wins; absence → silent skip.

YAML=""
FOUND_PATH=""
IFS=',' read -ra PATH_ARRAY <<< "$PATHS"
for raw_path in "${PATH_ARRAY[@]}"; do
    path="$(echo "$raw_path" | xargs)"
    [ -z "$path" ] && continue
    if [ -f "./$path" ]; then
        YAML=$(cat "./$path")
        FOUND_PATH="$path"
        break
    fi
done

if [ -z "$YAML" ]; then
    echo "No catalog-info.yaml at any of '$PATHS' in the checkout — skipping"
    exit 0
fi
echo "Read $FOUND_PATH from checkout (${#YAML} bytes)"

# --- Augment ---------------------------------------------------------------
# Hand the file to the shared pipeline (parse → match → transform → write).
# Identical to what main.sh does after fetching over the API.

# helpers.sh lives next to this script; resolved at runtime via dirname.
# shellcheck disable=SC1091
source "$(dirname "$0")/helpers.sh"
augment_component "$COMPONENT_ID" "$YAML"
