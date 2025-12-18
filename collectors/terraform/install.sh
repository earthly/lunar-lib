#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" == "Darwin" ]]; then
  brew list --formula hcl2json >/dev/null 2>&1 || brew install hcl2json
else
  URL="https://github.com/tmccombs/hcl2json/releases/latest/download/hcl2json_linux_amd64"
  TMP=$(mktemp)
  echo "Downloading $URL ..."
  curl -fsSL -o "$TMP" "$URL"
  chmod +x "$TMP"
  install -m 0755 "$TMP" /usr/local/bin/hcl2json 2>/dev/null
fi

echo "Terraform collector dependencies installed."