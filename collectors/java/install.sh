#!/bin/bash
set -e

OS=$(uname -s)
ARCH=$(uname -m)

# Map architecture
case "$ARCH" in
  x86_64) ARCHITECTURE="amd64" ;;
  arm64 | aarch64) ARCHITECTURE="arm64" ;;
  *)
    echo "Unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac

# Install Java if not present
if ! command -v java >/dev/null 2>&1; then
  echo "Installing Java for ${OS}_${ARCHITECTURE}..." >&2
  case "$OS" in
  Linux)
    if command -v apt-get >/dev/null 2>&1; then
      apt-get update && apt-get install -y openjdk-17-jdk || apt-get install -y default-jdk || true
    elif command -v yum >/dev/null 2>&1; then
      yum install -y java-17-openjdk-devel || yum install -y java-devel || true
    elif command -v apk >/dev/null 2>&1; then
      apk add --no-cache openjdk17 || apk add --no-cache openjdk || true
    else
      echo "No supported package manager found to install Java." >&2
    fi
    ;;
  Darwin)
    if command -v brew >/dev/null 2>&1; then
      brew install openjdk@17 || brew install openjdk || true
    else
      echo "Homebrew not found; please install Java manually on macOS." >&2
    fi
    ;;
  *)
    echo "Unsupported operating system: $OS" >&2
    exit 1
    ;;
  esac

  if ! command -v java >/dev/null 2>&1; then
    echo "Java is not installed and automatic install failed; please install Java on this runner." >&2
    exit 1
  fi
fi

# Verify Java installation
if command -v java >/dev/null 2>&1; then
  java_version=$(java -version 2>&1 | head -n1 || echo "unknown")
  echo "Java installed successfully: $java_version" >&2
else
  echo "Java installation verification failed." >&2
  exit 1
fi

