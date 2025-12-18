#!/bin/bash
set -e

# Detect platform
OS=$(uname -s)
ARCH=$(uname -m)

# Map to the naming convention used in the releases
case "$OS" in
    Linux)
        PLATFORM="Linux"
        INSTALL_DIR="/usr/local/bin"
        ;;
    Darwin)
        PLATFORM="Darwin"
        INSTALL_DIR="$HOME"/.lunar/bin
        ;;
    *)
        echo "Unsupported operating system: $OS"
        exit 1
        ;;
esac

case "$ARCH" in
    x86_64)
        ARCHITECTURE="x86_64"
        ;;
    arm64|aarch64)
        ARCHITECTURE="arm64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Download and install the appropriate binary
DOWNLOAD_URL="https://github.com/keilerkonzept/dockerfile-json/releases/download/v1.2.2/dockerfile-json_${PLATFORM}_${ARCHITECTURE}.tar.gz"
echo "Downloading dockerfile-json for ${PLATFORM}_${ARCHITECTURE}..."
curl -L "$DOWNLOAD_URL" | tar xz
mv dockerfile-json "$INSTALL_DIR/"

