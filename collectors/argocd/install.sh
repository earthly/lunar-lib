#!/bin/bash
set -e

# Configuration
YQ_VERSION="v4.44.3"

# Platform detection
detect_platform() {
    OS=$(uname -s)
    ARCH=$(uname -m)

    case "$OS" in
        Linux)
            PLATFORM="linux"
            INSTALL_DIR="/usr/local/bin"
            ;;
        Darwin)
            PLATFORM="darwin"
            INSTALL_DIR="$HOME/.lunar/bin"
            ;;
        *)
            echo "Unsupported operating system: $OS"
            exit 1
            ;;
    esac

    case "$ARCH" in
        x86_64)
            ARCHITECTURE="amd64"
            ;;
        arm64|aarch64)
            ARCHITECTURE="arm64"
            ;;
        *)
            echo "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac
}

# yq installation
install_yq() {
    local download_url="https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_${PLATFORM}_${ARCHITECTURE}"
    echo "Downloading yq ${YQ_VERSION} for ${PLATFORM}_${ARCHITECTURE}..."
    curl -L "$download_url" -o "$INSTALL_DIR/yq"
    chmod +x "$INSTALL_DIR/yq"
}

# GNU parallel installation
install_parallel() {
    if [[ "$PLATFORM" == "darwin" ]]; then
        # On macOS, use brew if available, otherwise download directly
        if command -v brew &> /dev/null; then
            brew install parallel
        else
            echo "Installing GNU parallel via direct download..."
            curl -sSL -o "$INSTALL_DIR/parallel" "https://raw.githubusercontent.com/martinda/gnu-parallel/master/src/parallel"
            chmod +x "$INSTALL_DIR/parallel"
        fi
    else
        # On Linux, download directly
        echo "Installing GNU parallel via direct download..."
        curl -sSL -o "$INSTALL_DIR/parallel" "https://raw.githubusercontent.com/martinda/gnu-parallel/master/src/parallel"
        chmod +x "$INSTALL_DIR/parallel"
    fi

    # Pre-accept citation prompt to avoid interactive runs
    printf 'will cite\n' | "$INSTALL_DIR/parallel" --citation >/dev/null 2>&1 || true
}

# Install backstage validator
DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends npm
npm install -g @roadiehq/backstage-entity-validator

# Install tools if not already present
detect_platform
mkdir -p "$INSTALL_DIR"

if ! command -v yq &> /dev/null; then
    echo "Installing yq..."
    install_yq
    echo "yq installed successfully"
else
    echo "yq is already installed"
fi

if ! command -v parallel &> /dev/null; then
    echo "Installing GNU parallel..."
    install_parallel
    echo "GNU parallel installed successfully"
else
    echo "GNU parallel is already installed"
fi

# Verify installations
echo "Verifying installations..."
yq --version
parallel --version | head -n 1