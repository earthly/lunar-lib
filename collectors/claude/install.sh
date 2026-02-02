#!/bin/bash

set -e

echo "Installing Claude CLI..."

# Install Claude CLI from official source
curl -fsSL https://claude.ai/install.sh | bash

# Verify installation
if command -v claude &> /dev/null; then
    echo "Claude CLI installed successfully: $(claude --version 2>/dev/null || echo 'version unknown')"
else
    # Check common installation paths
    if [ -x "$HOME/.local/bin/claude" ]; then
        echo "Claude CLI installed at $HOME/.local/bin/claude"
    else
        echo "Warning: Claude CLI installation may have failed"
        exit 1
    fi
fi


