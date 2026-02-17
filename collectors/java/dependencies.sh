#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Java project
if ! is_java_project; then
    echo "No Java project detected, exiting"
    exit 0
fi

# Try Maven pom.xml first
if [[ -f "pom.xml" ]]; then
    python3 - <<'PY' | lunar collect -j ".lang.java.dependencies" - || true
import json
import xml.etree.ElementTree as ET

try:
    tree = ET.parse("pom.xml")
    root = tree.getroot()
except Exception:
    import sys
    sys.exit(0)

# Handle Maven namespace
ns = {}
prefix = ""
if root.tag.startswith("{"):
    uri = root.tag[root.tag.find("{") + 1:root.tag.find("}")]
    ns["m"] = uri
    prefix = "m:"

# Collect <properties> for resolving ${variable} references
properties = {}
props_elem = root.find(f"./{prefix}properties", ns)
if props_elem is not None:
    for child in list(props_elem):
        tag = child.tag
        if tag.startswith("{"):
            tag = tag[tag.find("}") + 1:]
        properties[tag] = (child.text or "").strip()

deps = []
# Only scan direct <dependencies> block, skip dependencyManagement and plugin deps
deps_elem = root.find(f"./{prefix}dependencies", ns)
dep_list = deps_elem.findall(f"{prefix}dependency", ns) if deps_elem is not None else []
for dep in dep_list:
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

    deps.append({
        "path": f"{group}:{artifact}",
        "version": version,
        "indirect": False,
    })

print(json.dumps({
    "direct": deps,
    "transitive": [],
    "source": {"tool": "maven", "integration": "code"},
}))
PY
    exit 0
fi

# Try Gradle lockfile
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
            deps+=("$(jq -n --arg path "$group:$artifact" --arg version "$version" \
                '{path: $path, version: $version, indirect: false}')")
        fi
    done < gradle.lockfile

    if [[ ${#deps[@]} -gt 0 ]]; then
        jq -n \
            --argjson direct "$(printf '%s\n' "${deps[@]}" | jq -s '.')" \
            '{direct: $direct, transitive: [], source: {tool: "gradle", integration: "code"}}' | \
            lunar collect -j ".lang.java.dependencies" -
    else
        jq -n '{direct: [], transitive: [], source: {tool: "gradle", integration: "code"}}' | \
            lunar collect -j ".lang.java.dependencies" -
    fi
    exit 0
fi

echo "No pom.xml or gradle.lockfile found, exiting"
exit 0
