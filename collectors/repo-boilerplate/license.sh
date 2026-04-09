#!/bin/bash

set -e

# Check common LICENSE file variants
LICENSE_FILE=""
for candidate in LICENSE LICENSE.md LICENSE.txt LICENCE LICENCE.md LICENCE.txt; do
  if [ -f "./$candidate" ]; then
    LICENSE_FILE="./$candidate"
    break
  fi
done

if [ -z "$LICENSE_FILE" ]; then
  lunar collect -j ".repo.license.exists" false
  exit 0
fi

PATH_NORMALIZED="${LICENSE_FILE#./}"

# Try to identify SPDX license type from content
SPDX_ID=""
CONTENT=$(head -20 "$LICENSE_FILE" 2>/dev/null || true)

if echo "$CONTENT" | grep -qi "MIT License"; then
  SPDX_ID="MIT"
elif echo "$CONTENT" | grep -qi "Apache License.*Version 2"; then
  SPDX_ID="Apache-2.0"
elif echo "$CONTENT" | grep -qi "GNU GENERAL PUBLIC LICENSE" && echo "$CONTENT" | grep -qi "Version 3"; then
  SPDX_ID="GPL-3.0"
elif echo "$CONTENT" | grep -qi "GNU GENERAL PUBLIC LICENSE" && echo "$CONTENT" | grep -qi "Version 2"; then
  SPDX_ID="GPL-2.0"
elif echo "$CONTENT" | grep -qi "GNU LESSER GENERAL PUBLIC LICENSE"; then
  SPDX_ID="LGPL"
elif echo "$CONTENT" | grep -qi "BSD 3-Clause"; then
  SPDX_ID="BSD-3-Clause"
elif echo "$CONTENT" | grep -qi "BSD 2-Clause"; then
  SPDX_ID="BSD-2-Clause"
elif echo "$CONTENT" | grep -qi "Mozilla Public License.*2\.0"; then
  SPDX_ID="MPL-2.0"
elif echo "$CONTENT" | grep -qi "ISC License"; then
  SPDX_ID="ISC"
elif echo "$CONTENT" | grep -qi "The Unlicense"; then
  SPDX_ID="Unlicense"
fi

JSON=$(jq -n \
  --argjson exists true \
  --arg path "$PATH_NORMALIZED" \
  --arg spdx_id "$SPDX_ID" \
  '{
    exists: $exists,
    path: $path,
    spdx_id: (if $spdx_id == "" then null else $spdx_id end)
  }')

echo "$JSON" | lunar collect -j ".repo.license" -
