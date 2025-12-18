#!/bin/bash
set -e

# Detect platform and install tools
OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
Linux)
    # Map architecture
    case "$ARCH" in
    x86_64) ARCHITECTURE="amd64" ;;
    arm64 | aarch64) ARCHITECTURE="arm64" ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
    esac

    # Install kubeconform
    echo "Downloading kubeconform for linux_${ARCHITECTURE}..."
    curl -L "https://github.com/yannh/kubeconform/releases/latest/download/kubeconform-linux-${ARCHITECTURE}.tar.gz" | tar xz
    mv kubeconform /usr/local/bin/

    # Install GNU parallel via package manager
    echo "Installing GNU parallel..."
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update && apt-get install -y parallel
    elif command -v yum >/dev/null 2>&1; then
        yum install -y parallel
    elif command -v apk >/dev/null 2>&1; then
        apk add --no-cache parallel
    else
        # Fallback: download from GitHub mirror
        echo "Using GitHub mirror for parallel..."
        curl -L "https://raw.githubusercontent.com/martinda/gnu-parallel/master/src/parallel" -o /usr/local/bin/parallel
        chmod +x /usr/local/bin/parallel
    fi
    ;;
Darwin)
    # Map architecture
    case "$ARCH" in
    x86_64) ARCHITECTURE="amd64" ;;
    arm64 | aarch64) ARCHITECTURE="arm64" ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
    esac

    # Create install directory
    mkdir -p "$HOME/.lunar/bin"

    # Install kubeconform
    echo "Downloading kubeconform for darwin_${ARCHITECTURE}..."
    curl -L "https://github.com/yannh/kubeconform/releases/latest/download/kubeconform-darwin-${ARCHITECTURE}.tar.gz" | tar xz
    mv kubeconform "$HOME/.lunar/bin/"

    # Install GNU parallel
    echo "Installing GNU parallel..."
    brew install parallel
    ;;
*)
    echo "Unsupported operating system: $OS"
    exit 1
    ;;
esac
