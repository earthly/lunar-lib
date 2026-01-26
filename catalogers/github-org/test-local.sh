#!/bin/bash
set -e

# Local test script for github-org cataloger
# Creates a mock 'lunar' command and runs main.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
OUTPUT_FILE="$TEST_DIR/catalog-output.json"

echo "Test directory: $TEST_DIR"
echo "Output file: $OUTPUT_FILE"

# Create mock 'lunar' command
cat > "$TEST_DIR/lunar" << 'EOF'
#!/bin/bash
# Mock lunar command - captures catalog output to file

if [[ "$1" == "catalog" && "$2" == "--json" && "$3" == ".components" ]]; then
    # Read from stdin (the - argument) and append to output file
    cat >> "${LUNAR_TEST_OUTPUT_FILE}"
    echo ""  # Add newline between batches
else
    echo "Mock lunar: unhandled command: $@" >&2
    exit 1
fi
EOF
chmod +x "$TEST_DIR/lunar"

# Add mock to PATH
export PATH="$TEST_DIR:$PATH"
export LUNAR_TEST_OUTPUT_FILE="$OUTPUT_FILE"

# Initialize output file
echo "" > "$OUTPUT_FILE"

# Set cataloger inputs - use a small public org for testing
export LUNAR_VAR_ORG_NAME="${TEST_ORG:-earthly}"
export LUNAR_VAR_INCLUDE_PUBLIC="${TEST_INCLUDE_PUBLIC:-true}"
export LUNAR_VAR_INCLUDE_PRIVATE="${TEST_INCLUDE_PRIVATE:-false}"
export LUNAR_VAR_INCLUDE_INTERNAL="${TEST_INCLUDE_INTERNAL:-false}"
export LUNAR_VAR_INCLUDE_ARCHIVED="${TEST_INCLUDE_ARCHIVED:-false}"
export LUNAR_VAR_INCLUDE_REPOS="${TEST_INCLUDE_REPOS:-}"
export LUNAR_VAR_EXCLUDE_REPOS="${TEST_EXCLUDE_REPOS:-}"
export LUNAR_VAR_TAG_PREFIX="${TEST_TAG_PREFIX:-gh-}"
export LUNAR_VAR_DEFAULT_OWNER="${TEST_DEFAULT_OWNER:-}"

echo ""
echo "=== Running cataloger with settings ==="
echo "Org: $LUNAR_VAR_ORG_NAME"
echo "Include public: $LUNAR_VAR_INCLUDE_PUBLIC"
echo "Include private: $LUNAR_VAR_INCLUDE_PRIVATE"
echo "Include internal: $LUNAR_VAR_INCLUDE_INTERNAL"
echo "Include archived: $LUNAR_VAR_INCLUDE_ARCHIVED"
echo "Include repos: $LUNAR_VAR_INCLUDE_REPOS"
echo "Exclude repos: $LUNAR_VAR_EXCLUDE_REPOS"
echo "Tag prefix: $LUNAR_VAR_TAG_PREFIX"
echo "Default owner: $LUNAR_VAR_DEFAULT_OWNER"
echo ""
echo "=== Cataloger output ==="

# Run the cataloger
"$SCRIPT_DIR/main.sh"

echo ""
echo "=== Captured catalog JSON ==="
# Show the output, merging multiple batch outputs into one object
jq -s 'add' "$OUTPUT_FILE" 2>/dev/null || cat "$OUTPUT_FILE"

echo ""
echo "=== Component count ==="
jq -s 'add | keys | length' "$OUTPUT_FILE" 2>/dev/null || echo "Could not count"

# Cleanup
rm -rf "$TEST_DIR"
