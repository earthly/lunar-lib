#!/bin/bash

set -euo pipefail

# .NET Dependencies Collector
# Extracts NuGet dependencies and project references

# Check for .NET project indicators
has_dotnet_project() {
    find . -maxdepth 3 \( \
        -name "*.csproj" -o \
        -name "*.fsproj" -o \
        -name "*.vbproj" \
        \) -print -quit | grep -q .
}

# Skip if no .NET project files found
if ! has_dotnet_project; then
    echo "{}"
    exit 0
fi

# Initialize Python processor for dependencies
python3 << 'EOF'
import json
import xml.etree.ElementTree as ET
from pathlib import Path

def parse_xml_safely(file_path):
    """Parse XML file safely, handling encoding issues."""
    try:
        tree = ET.parse(file_path)
        return tree.getroot()
    except ET.ParseError:
        for encoding in ['utf-8', 'utf-16', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                return ET.fromstring(content)
            except (UnicodeDecodeError, ET.ParseError):
                continue
    except Exception:
        pass
    return None

def find_project_files():
    """Find all .NET project files."""
    patterns = ["*.csproj", "*.fsproj", "*.vbproj"]
    files = []
    for pattern in patterns:
        for depth in range(1, 4):  # Search up to 3 levels deep
            for file in Path('.').glob('/'.join(['*'] * (depth - 1) + [pattern])):
                if file.is_file():
                    files.append(str(file))
    return files

def extract_package_references(root):
    """Extract NuGet package references from project XML."""
    if root is None:
        return []

    packages = []

    # Find all PackageReference elements
    for pkg_ref in root.findall('.//PackageReference'):
        include = pkg_ref.get('Include')
        version = pkg_ref.get('Version')

        if include:
            package_info = {
                "name": include,
                "type": "package"
            }

            if version:
                package_info["version"] = version
            else:
                # Version might be in child element
                version_elem = pkg_ref.find('Version')
                if version_elem is not None and version_elem.text:
                    package_info["version"] = version_elem.text.strip()

            packages.append(package_info)

    return packages

def extract_project_references(root):
    """Extract project references from project XML."""
    if root is None:
        return []

    project_refs = []

    # Find all ProjectReference elements
    for proj_ref in root.findall('.//ProjectReference'):
        include = proj_ref.get('Include')

        if include:
            # Normalize path separators
            normalized_path = include.replace('\\', '/')
            project_refs.append({
                "path": normalized_path
            })

    return project_refs

# Main dependencies collection
result = {
    "source": {"tool": "dotnet", "integration": "code"}
}

project_files = find_project_files()

if not project_files:
    print(json.dumps({}))
    exit()

all_packages = []
all_project_refs = []

# Process each project file
for proj_file in project_files:
    root = parse_xml_safely(proj_file)

    if root is not None:
        # Extract package references
        packages = extract_package_references(root)
        all_packages.extend(packages)

        # Extract project references
        project_refs = extract_project_references(root)
        all_project_refs.extend(project_refs)

# Remove duplicates while preserving order
def deduplicate_list(items, key_func):
    seen = set()
    result = []
    for item in items:
        key = key_func(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

# Deduplicate packages by name
unique_packages = deduplicate_list(
    all_packages,
    lambda x: x["name"]
)

# Deduplicate project references by path
unique_project_refs = deduplicate_list(
    all_project_refs,
    lambda x: x["path"]
)

# Build final result
if unique_packages or unique_project_refs:
    if unique_packages:
        result["direct"] = unique_packages
    else:
        result["direct"] = []

    if unique_project_refs:
        result["project_references"] = unique_project_refs

print(json.dumps(result, indent=2))
EOF