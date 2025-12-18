#!/bin/bash
set -e

# Check if this is actually a Node.js project by looking for package.json
if [[ ! -f "package.json" ]]; then
    echo "No package.json found, exiting"
    exit 0
fi

if [[ -f "package.json" ]]; then
  jq -n --slurpfile pkg package.json '
    {
      direct: (
        ($pkg[0].dependencies // {}) | to_entries | map({path: .key, version: .value, indirect: false, replace: null, license: ""})
      ),
      transitive: []
    }
  ' | lunar collect -j ".lang.nodejs.dependencies" -
fi

