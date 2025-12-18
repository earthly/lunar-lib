#!/bin/bash

set -e

if [ -f ./README.md ]; then
  lunar collect -j \
    "repo.readme_exists" true \
    "repo.readme_num_lines" "$(wc -l < ./README.md)"
else
  lunar collect -j "repo.readme_exists" false
fi
