#!/bin/bash
set -e

# Collect Rust dependencies from Cargo.toml and Cargo.lock

if [[ ! -f "Cargo.toml" ]]; then
    echo "No Cargo.toml found, exiting"
    exit 0
fi

# Parse dependencies from a Cargo.toml section into JSON lines
# Uses grep+sed for reliable parsing across awk implementations
parse_toml_deps() {
    local section="$1"
    local in_section=false
    local line

    while IFS= read -r line; do
        # Detect section headers
        if [[ "$line" == "[$section]" ]]; then
            in_section=true
            continue
        elif [[ "$line" == "[$section."* ]]; then
            # Sub-table like [dependencies.serde] — skip (handle inline only)
            in_section=false
            continue
        elif [[ "$line" == "["* ]]; then
            in_section=false
            continue
        fi

        if [[ "$in_section" != "true" ]]; then
            continue
        fi

        # Skip empty lines and comments
        [[ -z "$line" || "$line" == "#"* ]] && continue

        # Extract dependency name (before first =)
        local name="${line%%=*}"
        name="$(echo "$name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [[ -z "$name" ]] && continue

        # Extract the value part (after first =)
        local value="${line#*=}"
        value="$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

        local version=""
        local features="[]"

        if [[ "$value" == "{"* ]]; then
            # Table form: { version = "1.0", features = ["derive"] }
            version=$(echo "$value" | grep -oP 'version\s*=\s*"\K[^"]+' 2>/dev/null || true)
            local feat_raw=$(echo "$value" | grep -oP 'features\s*=\s*\[\K[^\]]+' 2>/dev/null || true)
            if [[ -n "$feat_raw" ]]; then
                features=$(echo "$feat_raw" | sed 's/"//g; s/[[:space:]]//g' | awk -F, '{
                    printf "["
                    for(i=1;i<=NF;i++) {
                        if(i>1) printf ","
                        printf "\"%s\"", $i
                    }
                    printf "]"
                }')
            fi
        elif [[ "$value" == '"'* ]]; then
            # Simple form: "1.0"
            version=$(echo "$value" | sed 's/"//g')
        fi

        printf '{"path":"%s","version":"%s","features":%s}\n' "$name" "$version" "$features"
    done < Cargo.toml
}

# Parse each section
direct_json=$(parse_toml_deps "dependencies" | jq -s '. // []')
dev_json=$(parse_toml_deps "dev-dependencies" | jq -s '. // []')
build_json=$(parse_toml_deps "build-dependencies" | jq -s '. // []')

# Parse transitive deps from Cargo.lock if present
transitive_json="[]"
if [[ -f "Cargo.lock" ]]; then
    # Get direct dep names to exclude from transitive list
    direct_names=$(echo "$direct_json" "$dev_json" "$build_json" | jq -s 'add | map(.path) | unique')

    # Parse [[package]] entries from Cargo.lock
    transitive_json=$(awk '
        /^\[\[package\]\]/ { name=""; version=""; next }
        /^name = / { gsub(/"/, "", $3); name=$3 }
        /^version = / { gsub(/"/, "", $3); version=$3 }
        /^$/ || /^\[/ {
            if (name != "" && version != "") {
                printf "{\"path\":\"%s\",\"version\":\"%s\"}\n", name, version
            }
            name=""; version=""
        }
        END {
            if (name != "" && version != "") {
                printf "{\"path\":\"%s\",\"version\":\"%s\"}\n", name, version
            }
        }
    ' Cargo.lock | jq -s --argjson direct_names "$direct_names" '
        [.[] | select(.path as $p | $direct_names | index($p) | not)]
    ')
fi

# Build and collect
jq -n \
    --argjson direct "$direct_json" \
    --argjson dev "$dev_json" \
    --argjson build "$build_json" \
    --argjson transitive "$transitive_json" \
    '{
        direct: $direct,
        dev: $dev,
        build: $build,
        transitive: $transitive,
        source: {
            tool: "cargo",
            integration: "code"
        }
    }' | lunar collect -j ".lang.rust.dependencies" -
