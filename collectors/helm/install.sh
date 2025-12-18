#!/bin/bash

set -e

# Detect platform
OS=$(uname -s)
ARCH=$(uname -m)

# Map to the naming convention used in the releases (Ubuntu/Linux and macOS only)
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

# Create install directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Install Helm if not already installed (download binary directly; no Homebrew, no install script)
if ! command -v helm &> /dev/null; then
  echo "Installing Helm..."
  HELM_VERSION="v3.13.3"
  DOWNLOAD_URL="https://get.helm.sh/helm-${HELM_VERSION}-${PLATFORM}-${ARCHITECTURE}.tar.gz"
  echo "Downloading Helm ${HELM_VERSION} for ${PLATFORM}_${ARCHITECTURE}..."
  curl -L "$DOWNLOAD_URL" | tar xz
  mv "${PLATFORM}-${ARCHITECTURE}/helm" "$INSTALL_DIR/"
  rm -rf "${PLATFORM}-${ARCHITECTURE}"
  echo "Helm installed successfully"
else
  echo "Helm is already installed"
fi

# Verify installation
helm version --short

# Install GNU parallel for concurrent processing via curl (no sudo, mac/Linux)
if ! command -v parallel &> /dev/null; then
  echo "Installing GNU parallel..."
  # Try package manager first, fallback to GitHub mirror
  if command -v brew >/dev/null 2>&1; then
      brew install parallel
  elif command -v apt-get >/dev/null 2>&1; then
      apt-get update && apt-get install -y parallel
  else
      # Fallback: download from GitHub mirror
      echo "Using GitHub mirror for parallel..."
      PARALLEL_URL="https://raw.githubusercontent.com/martinda/gnu-parallel/master/src/parallel"
      curl -fsSL -o "$INSTALL_DIR/parallel" "$PARALLEL_URL"
      chmod +x "$INSTALL_DIR/parallel"
  fi
  # Pre-accept citation prompt to avoid interactive runs
  printf 'will cite\n' | "$INSTALL_DIR/parallel" --citation >/dev/null 2>&1 || true
  echo "GNU parallel installed"
else
  echo "GNU parallel is already installed"
fi
