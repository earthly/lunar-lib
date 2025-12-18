#!/bin/bash
set -e

# Check if this is actually a Java project by looking for .java files
if ! find . -name "*.java" -type f 2>/dev/null | grep -q .; then
    echo "No Java files found, exiting"
    exit 0
fi

# Try Maven pom.xml first
if [[ -f "pom.xml" ]]; then
  python3 - <<'PY' | lunar collect -j ".lang.java.dependencies" - || true
import json
import sys
import xml.etree.ElementTree as ET

try:
    tree = ET.parse("pom.xml")
    root = tree.getroot()
except Exception:
    sys.exit(0)

ns = {}
if root.tag.startswith("{"):
    uri = root.tag[root.tag.find("{")+1:root.tag.find("}")]
    ns["m"] = uri
    prefix = "m:"
else:
    prefix = ""

# Collect <properties> so we can resolve versions like ${junit.version}
properties = {}
props_elem = root.find(f"./{prefix}properties", ns)
if props_elem is not None:
    for child in list(props_elem):
        tag = child.tag
        if tag.startswith("{"):
            tag = tag[tag.find("}")+1:]
        properties[tag] = (child.text or "").strip()

deps = []
for dep in root.findall(f".//{prefix}dependency", ns):
    group = dep.findtext(f"{prefix}groupId", default="", namespaces=ns)
    artifact = dep.findtext(f"{prefix}artifactId", default="", namespaces=ns)
    version = dep.findtext(f"{prefix}version", default="", namespaces=ns) or ""
    version = version.strip()

    # Resolve property references like ${junit.version}
    if version.startswith("${") and version.endswith("}"):
        prop_name = version[2:-1].strip()
        resolved = properties.get(prop_name)
        if resolved:
            version = resolved

    scope = dep.findtext(f"{prefix}scope", default="", namespaces=ns)
    deps.append({
        "path": f"{group}:{artifact}",
        "version": version,
        "indirect": False,
        "replace": None,
        "license": ""
    })

print(json.dumps({"direct": deps, "transitive": []}))
PY
  exit 0
fi

# Next, try Gradle lockfile
if [[ -f "gradle.lockfile" ]]; then
  deps=()
  while IFS= read -r line; do
    clean=$(echo "$line" | sed 's/#.*//' | tr -d '[:space:]')
    if [[ -z "$clean" ]]; then
      continue
    fi
    coord="${clean%%=*}"
    IFS=':' read -r group artifact version <<<"$coord"
    if [[ -n "$group" && -n "$artifact" && -n "$version" ]]; then
      deps+=("$(jq -n --arg group "$group" --arg artifact "$artifact" --arg version "$version" '{group: $group, artifact: $artifact, version: $version}')")
    fi
  done < gradle.lockfile

  jq -n --argjson direct "$(printf '%s\n' "${deps[@]}" | jq -s 'map({path: (.group + ":" + .artifact), version: .version, indirect: false, replace: null, license: ""})')" \
    '{direct: $direct, transitive: []}' | lunar collect -j ".lang.java.dependencies" -
  exit 0
fi

# No build files found, exit without collecting
echo "No pom.xml or gradle.lockfile found, exiting"
exit 0

