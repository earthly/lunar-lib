#!/bin/bash
set -e

# Install jq, used by cli.sh to normalize Snyk JSON results into severity
# counts. The CLI collector runs native on the CI runner, so jq may not be
# present — cli.sh degrades gracefully if this install is skipped or fails,
# but having jq is what unlocks the .sca.vulnerabilities / .summary fields.
if command -v jq >/dev/null 2>&1; then
    echo "jq already available"
    exit 0
fi

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

# jq release assets use "macos" rather than "darwin".
case "$OS" in
    darwin) OS="macos" ;;
esac

case "$ARCH" in
    x86_64)        ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *)             echo "Unsupported architecture: $ARCH" >&2; exit 0 ;;
esac

JQ_VERSION="1.7.1"
JQ_URL="https://github.com/jqlang/jq/releases/download/jq-${JQ_VERSION}/jq-${OS}-${ARCH}"

echo "Installing jq ${JQ_VERSION}..."
curl -sL "$JQ_URL" -o "${LUNAR_BIN_DIR}/jq"
chmod +x "${LUNAR_BIN_DIR}/jq"
echo "jq installed successfully"
