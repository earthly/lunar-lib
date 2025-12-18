#!/bin/bash

set -e

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

# Generic tool installer
install_tool() {
    local tool_name="$1"
    local check_cmd="$2"
    local install_func="$3"

    if ! command -v "$check_cmd" &> /dev/null; then
        echo "Installing $tool_name..."
        $install_func
        echo "$tool_name installed successfully"
    else
        echo "$tool_name is already installed"
    fi
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
            # Pre-accept citation prompt to avoid interactive runs
            printf 'will cite\n' | "$INSTALL_DIR/parallel" --citation >/dev/null 2>&1 || true
        fi
    else
        # On Linux, download directly
        echo "Installing GNU parallel via direct download..."
        curl -sSL -o "$INSTALL_DIR/parallel" "https://raw.githubusercontent.com/martinda/gnu-parallel/master/src/parallel"
        chmod +x "$INSTALL_DIR/parallel"
        # Pre-accept citation prompt to avoid interactive runs
        printf 'will cite\n' | "$INSTALL_DIR/parallel" --citation >/dev/null 2>&1 || true
    fi
}

# Main installation process
main() {
    detect_platform
    mkdir -p "$INSTALL_DIR"

    install_tool "yq" "yq" "install_yq"
    install_tool "GNU parallel" "parallel" "install_parallel"

    # Verify installations
    echo "Verifying installations..."
    yq --version
    parallel --version | head -n 1

    echo "All tools installed successfully!"
}

main "$@"