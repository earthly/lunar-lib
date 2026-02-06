#!/bin/bash
set -e

# Install the syft SBOM generator if not already present.
if command -v syft >/dev/null 2>&1; then
  echo "syft is already installed"
  exit 0
fi

OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
  Linux) PLATFORM="linux" ;;
  Darwin) PLATFORM="darwin" ;;
  *)
    echo "Unsupported operating system: $OS"
    exit 1
    ;;
esac

case "$ARCH" in
  x86_64) ARCHITECTURE="amd64" ;;
  arm64|aarch64) ARCHITECTURE="arm64" ;;
  *)
    echo "Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

# Install Python if not present (needed for Python license detection)
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "Installing Python..." >&2
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache python3 py3-pip || true
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update && apt-get install -y python3 python3-pip || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 python3-pip || true
  elif command -v brew >/dev/null 2>&1; then
    brew install python3 || true
  else
    echo "No supported package manager found to install Python." >&2
  fi

  if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo "Python install failed; Python license detection may be unavailable." >&2
  fi
fi

INSTALL_DIR="/usr/local/bin"
VERSION="v1.19.0"
TAR_NAME="syft_${VERSION#v}_${PLATFORM}_${ARCHITECTURE}.tar.gz"
DOWNLOAD_URL="https://github.com/anchore/syft/releases/download/${VERSION}/${TAR_NAME}"

echo "Downloading syft ${VERSION} for ${PLATFORM}_${ARCHITECTURE}..."
curl -sSfL "$DOWNLOAD_URL" | tar xz

if [ ! -f syft ]; then
  echo "syft binary not found after extraction"
  exit 1
fi

chmod +x syft
mv syft "$INSTALL_DIR/"
echo "syft installed to $INSTALL_DIR"
