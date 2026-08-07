#!/bin/bash
set -e

# shellcheck source=/dev/null
source "$(dirname "$0")/helpers.sh"

# Skip when no Kotlin source — Gradle/Maven-for-Java repos belong under .lang.java.
if ! is_kotlin_project; then
    echo "No Kotlin source files detected, exiting"
    exit 0
fi

# Maven (kotlin-maven-plugin): parse pom.xml with property resolution.
if pom_has_kotlin_plugin; then
    python3 - <<'PY' | lunar collect -j ".lang.kotlin.dependencies" - || true
import json
import sys
import xml.etree.ElementTree as ET

try:
    tree = ET.parse("pom.xml")
    root = tree.getroot()
except Exception:
    sys.exit(0)

prefix = ""
ns = {}
if root.tag.startswith("{"):
    uri = root.tag[root.tag.find("{") + 1:root.tag.find("}")]
    ns["m"] = uri
    prefix = "m:"

properties = {}
props_elem = root.find(f"./{prefix}properties", ns)
if props_elem is not None:
    for child in list(props_elem):
        tag = child.tag
        if tag.startswith("{"):
            tag = tag[tag.find("}") + 1:]
        properties[tag] = (child.text or "").strip()

deps = []
deps_elem = root.find(f"./{prefix}dependencies", ns)
dep_list = deps_elem.findall(f"{prefix}dependency", ns) if deps_elem is not None else []
for dep in dep_list:
    group = dep.findtext(f"{prefix}groupId", default="", namespaces=ns)
    artifact = dep.findtext(f"{prefix}artifactId", default="", namespaces=ns)
    version = (dep.findtext(f"{prefix}version", default="", namespaces=ns) or "").strip()
    if version.startswith("${") and version.endswith("}"):
        version = properties.get(version[2:-1].strip(), "")
    deps.append({"path": f"{group}:{artifact}", "version": version})

print(json.dumps({
    "direct": deps,
    "transitive": [],
    "source": {"tool": "maven", "integration": "code"},
}))
PY
    exit 0
fi

# Gradle: parse direct deps from build files + the version catalog, transitive
# from gradle.lockfile when present.
if [[ -f "build.gradle.kts" || -f "build.gradle" ]]; then
    python3 - <<'PY' | lunar collect -j ".lang.kotlin.dependencies" - || true
import json
import os
import re

CONFIGS = (
    "implementation|api|compileOnly|runtimeOnly|testImplementation|testApi|"
    "testCompileOnly|testRuntimeOnly|androidTestImplementation|debugImplementation|"
    "releaseImplementation|kapt|ksp|annotationProcessor|classpath"
)
# config("group:artifact:version")  or  config 'group:artifact:version'
LITERAL = re.compile(
    r'(?:' + CONFIGS + r')\s*\(?\s*["\']([^"\':]+:[^"\':]+:[^"\']+)["\']'
)


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


seen = set()
direct = []


def add(path, version):
    key = path
    if key in seen or path.count(":") != 1:
        return
    seen.add(key)
    direct.append({"path": path, "version": version})


for f in ("build.gradle.kts", "build.gradle"):
    if not os.path.exists(f):
        continue
    for coord in LITERAL.findall(read(f)):
        group, artifact, version = coord.split(":", 2)
        # Unresolved Groovy/Kotlin interpolation ("...:$ver") — keep path, drop version.
        if version.startswith("$") or "${" in version:
            version = ""
        add(f"{group}:{artifact}", version)

# Version catalog: [versions] key=val, [libraries] module + version.ref / version.
catalog = "gradle/libs.versions.toml"
if os.path.exists(catalog):
    versions = {}
    section = None
    for raw in read(catalog).splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section == "versions":
            m = re.match(r'([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"', line)
            if m:
                versions[m.group(1)] = m.group(2)
    section = None
    for raw in read(catalog).splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section != "libraries":
            continue
        # key = "group:artifact:version"
        m = re.match(r'[A-Za-z0-9_.-]+\s*=\s*"([^"]+:[^"]+:[^"]+)"', line)
        if m:
            group, artifact, version = m.group(1).split(":", 2)
            add(f"{group}:{artifact}", version)
            continue
        # key = { module = "group:artifact", version(.ref) = "..." }
        mod = re.search(r'module\s*=\s*"([^"]+:[^"]+)"', line)
        if not mod:
            grp = re.search(r'group\s*=\s*"([^"]+)"', line)
            nm = re.search(r'name\s*=\s*"([^"]+)"', line)
            module = f"{grp.group(1)}:{nm.group(1)}" if grp and nm else None
        else:
            module = mod.group(1)
        if not module:
            continue
        ref = re.search(r'version\.ref\s*=\s*"([^"]+)"', line)
        lit = re.search(r'version\s*=\s*"([^"]+)"', line)
        version = versions.get(ref.group(1), "") if ref else (lit.group(1) if lit else "")
        add(module, version)

# Transitive: gradle.lockfile -> "group:artifact:version=classpaths"
transitive = []
if os.path.exists("gradle.lockfile"):
    direct_paths = {d["path"] for d in direct}
    for raw in read("gradle.lockfile").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        coord = line.split("=", 1)[0]
        parts = coord.split(":")
        if len(parts) != 3:
            continue
        path = f"{parts[0]}:{parts[1]}"
        if path in direct_paths:
            continue
        transitive.append({"path": path, "version": parts[2]})

print(json.dumps({
    "direct": direct,
    "transitive": transitive,
    "source": {"tool": "gradle", "integration": "code"},
}))
PY
    exit 0
fi

echo "No Kotlin build manifest with parseable dependencies found, exiting"
exit 0
