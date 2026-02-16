#!/bin/bash
set -e

# Install yq for XML parsing (used by test-coverage sub-collector)
if command -v yq >/dev/null 2>&1; then
    echo "yq already available"
    exit 0
fi

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$ARCH" in
    x86_64)       ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *)            echo "Unsupported architecture: $ARCH" >&2; exit 0 ;;
esac

YQ_VERSION="v4.44.1"
YQ_URL="https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_${OS}_${ARCH}"

echo "Installing yq ${YQ_VERSION}..."
curl -sL "$YQ_URL" -o "${LUNAR_BIN_DIR}/yq"
chmod +x "${LUNAR_BIN_DIR}/yq"
echo "yq installed successfully"
