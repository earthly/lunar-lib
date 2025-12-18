#!/bin/bash
set -e

OS=$(uname -s)
ARCH=$(uname -m)

# Map architecture
case "$ARCH" in
  x86_64) ARCHITECTURE="amd64" ;;
  arm64 | aarch64) ARCHITECTURE="arm64" ;;
  *)
    echo "Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

# Install Go if not present
if ! command -v go >/dev/null 2>&1; then
  case "$OS" in
  Linux)
    if command -v apt-get >/dev/null 2>&1; then
      apt-get update && apt-get install -y golang || true
    elif command -v yum >/dev/null 2>&1; then
      yum install -y golang || true
    elif command -v apk >/dev/null 2>&1; then
      apk add --no-cache go || true
    else
      echo "No supported package manager found to install Go." >&2
    fi
    ;;
  Darwin)
    if command -v brew >/dev/null 2>&1; then
      brew install go || true
    else
      echo "Homebrew not found; please install Go manually on macOS." >&2
    fi
    ;;
  *)
    echo "Unsupported operating system: $OS"
    exit 1
    ;;
  esac

  if ! command -v go >/dev/null 2>&1; then
    echo "Go is not installed and automatic install failed; please install Go on this runner." >&2
    exit 1
  fi
fi

# Install golangci-lint if not present
if ! command -v golangci-lint >/dev/null 2>&1; then
  case "$OS" in
  Linux)
    echo "Installing golangci-lint for linux_${ARCHITECTURE}..."
    curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b /usr/local/bin v1.57.1 || true
    ;;
  Darwin)
    echo "Installing golangci-lint for darwin_${ARCHITECTURE}..."
    if command -v brew >/dev/null 2>&1; then
      brew install golangci-lint || true
    else
      curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b /usr/local/bin v1.57.1 || true
    fi
    ;;
  *)
    echo "Unsupported operating system for golangci-lint installation: $OS"
    ;;
  esac
fi