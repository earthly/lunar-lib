#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a .NET project
if ! is_dotnet_project; then
    echo "No .NET project detected, exiting"
    exit 0
fi

# Use Python for XML parsing of PackageReference and ProjectReference elements
python3 - <<'PY' | lunar collect -j ".lang.dotnet.dependencies" - || true
import json
import os
import xml.etree.ElementTree as ET

MSBUILD_NS = "{http://schemas.microsoft.com/developer/msbuild/2003}"


def find_all_elements(root, tag):
    """Find all elements with or without MSBuild namespace."""
    elements = root.findall(f".//{tag}")
    elements.extend(root.findall(f".//{MSBUILD_NS}{tag}"))
    return elements


def parse_deps(path):
    """Parse PackageReference and ProjectReference from a project file."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception:
        return [], []

    packages = []
    for pr in find_all_elements(root, "PackageReference"):
        include = pr.get("Include", "") or pr.get("include", "")
        if not include:
            continue
        # Version can be an attribute or child element
        version = pr.get("Version", "") or pr.get("version", "")
        if not version:
            ver_elem = pr.find("Version")
            if ver_elem is None:
                ver_elem = pr.find(f"{MSBUILD_NS}Version")
            if ver_elem is not None and ver_elem.text:
                version = ver_elem.text.strip()
        packages.append({
            "name": include,
            "version": version,
            "type": "package",
        })

    proj_refs = []
    for pr in find_all_elements(root, "ProjectReference"):
        include = pr.get("Include", "") or pr.get("include", "")
        if include:
            # Normalize path separators
            include = include.replace("\\", "/")
            proj_refs.append({"path": include})

    return packages, proj_refs


# Find all project files
all_packages = []
all_proj_refs = []
seen_packages = set()

for root_dir, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for f in files:
        if f.endswith((".csproj", ".fsproj", ".vbproj")):
            path = os.path.join(root_dir, f)
            packages, proj_refs = parse_deps(path)

            for pkg in packages:
                key = (pkg["name"].lower(), pkg["version"])
                if key not in seen_packages:
                    seen_packages.add(key)
                    all_packages.append(pkg)

            all_proj_refs.extend(proj_refs)

if not all_packages and not all_proj_refs:
    import sys
    print("No dependencies found", file=sys.stderr)
    sys.exit(0)

output = {
    "direct": all_packages,
    "source": {"tool": "dotnet", "integration": "code"},
}
if all_proj_refs:
    output["project_references"] = all_proj_refs

print(json.dumps(output))
PY
