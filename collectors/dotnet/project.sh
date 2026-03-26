#!/bin/bash

set -euo pipefail

# .NET Project Collector
# Detects .NET project structure, frameworks, and metadata

# Check for .NET project indicators
has_dotnet_project() {
    find . -maxdepth 3 \( \
        -name "*.csproj" -o \
        -name "*.fsproj" -o \
        -name "*.vbproj" -o \
        -name "*.sln" -o \
        -name "global.json" -o \
        -name "Directory.Build.props" \
        \) -print -quit | grep -q .
}

# Skip if no .NET indicators found
if ! has_dotnet_project; then
    echo "{}"
    exit 0
fi

# Initialize Python processor
python3 << 'EOF'
import json
import os
import xml.etree.ElementTree as ET
import re
from pathlib import Path

def find_files(patterns, max_depth=3):
    """Find files matching patterns up to max_depth."""
    files = []
    for pattern in patterns:
        for depth in range(1, max_depth + 1):
            for file in Path('.').glob('/'.join(['*'] * (depth - 1) + [pattern])):
                if file.is_file():
                    files.append(str(file))
    return files

def parse_xml_safely(file_path):
    """Parse XML file safely, handling encoding issues."""
    try:
        # Try to parse directly first
        tree = ET.parse(file_path)
        return tree.getroot()
    except ET.ParseError:
        # If that fails, try reading with different encodings
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

def get_project_type(root):
    """Determine project type from XML."""
    if root is None:
        return "unknown"

    # Check OutputType
    output_type = root.find('.//OutputType')
    if output_type is not None:
        output_val = output_type.text.lower() if output_type.text else ""
        if output_val == "exe":
            return "console"
        elif output_val == "library":
            return "library"
        elif output_val == "winexe":
            return "windows"

    # Check for web project indicators
    web_indicators = [
        './/PackageReference[@Include="Microsoft.AspNetCore.App"]',
        './/PackageReference[@Include="Microsoft.NET.Sdk.Web"]',
        './/Sdk[@Name="Microsoft.NET.Sdk.Web"]'
    ]
    for indicator in web_indicators:
        if root.find(indicator) is not None:
            return "web"

    # Check for test project indicators
    test_packages = [
        "Microsoft.NET.Test.Sdk",
        "xunit",
        "NUnit",
        "MSTest.TestFramework"
    ]
    for package in test_packages:
        if root.find(f'.//PackageReference[@Include="{package}"]') is not None:
            return "test"

    # Check SDK attribute
    project_elem = root.find('.')
    if project_elem is not None and project_elem.get('Sdk'):
        sdk = project_elem.get('Sdk', '')
        if 'Web' in sdk:
            return "web"
        elif 'Test' in sdk:
            return "test"

    # Default to library for SDK-style projects without OutputType
    return "library"

def get_target_framework(root):
    """Extract target framework from project XML."""
    if root is None:
        return None

    # Try TargetFramework first (single framework)
    tf = root.find('.//TargetFramework')
    if tf is not None and tf.text:
        return tf.text.strip()

    # Try TargetFrameworks (multiple frameworks, return first)
    tfs = root.find('.//TargetFrameworks')
    if tfs is not None and tfs.text:
        frameworks = [f.strip() for f in tfs.text.split(';') if f.strip()]
        return frameworks[0] if frameworks else None

    return None

def is_test_project(root, file_path):
    """Determine if project is a test project."""
    if root is None:
        return False

    # Check project type
    if get_project_type(root) == "test":
        return True

    # Check file path patterns
    path_lower = file_path.lower()
    if any(pattern in path_lower for pattern in ['test', 'tests', 'spec', 'specs']):
        return True

    return False

def get_test_framework(root):
    """Identify test framework being used."""
    if root is None:
        return None

    test_frameworks = {
        'xunit': ['xunit', 'xunit.core'],
        'nunit': ['NUnit', 'nunit'],
        'mstest': ['MSTest.TestFramework', 'Microsoft.VisualStudio.TestTools.UnitTesting']
    }

    for framework, packages in test_frameworks.items():
        for package in packages:
            if root.find(f'.//PackageReference[@Include="{package}"]') is not None:
                return framework

    return None

def parse_global_json():
    """Parse global.json for SDK version."""
    global_json_path = Path('global.json')
    if global_json_path.exists():
        try:
            with open(global_json_path) as f:
                data = json.load(f)
                return data.get('sdk', {}).get('version')
        except:
            pass
    return None

# Main collection logic
result = {
    "source": {"tool": "dotnet", "integration": "code"}
}

# Find project files
project_patterns = ["*.csproj", "*.fsproj", "*.vbproj"]
project_files = find_files(project_patterns)

# Find solution files
solution_files = find_files(["*.sln"])

# Check for special files
global_json_exists = Path('global.json').exists()
directory_build_props_exists = Path('Directory.Build.props').exists()
packages_lock_exists = len(find_files(["packages.lock.json"])) > 0

# Parse SDK version from global.json
sdk_version = parse_global_json()

# Process project files
project_data = []
target_frameworks = set()
test_projects = []

for proj_file in project_files:
    root = parse_xml_safely(proj_file)

    # Determine project language from extension
    ext = Path(proj_file).suffix.lower()
    proj_type = {
        '.csproj': 'csharp',
        '.fsproj': 'fsharp',
        '.vbproj': 'vb.net'
    }.get(ext, 'unknown')

    # Get project details
    output_type = get_project_type(root)
    target_framework = get_target_framework(root)

    if target_framework:
        target_frameworks.add(target_framework)

    project_info = {
        "path": proj_file,
        "type": proj_type,
        "output_type": output_type,
        "target_framework": target_framework
    }

    project_data.append(project_info)

    # Check if this is a test project
    if is_test_project(root, proj_file):
        test_framework = get_test_framework(root)
        test_info = {
            "path": proj_file,
            "type": proj_type,
            "test_framework": test_framework
        }
        test_projects.append(test_info)

# Compile results
if project_files or solution_files or global_json_exists or directory_build_props_exists:
    if sdk_version:
        result["sdk_version"] = sdk_version

    if target_frameworks:
        result["target_frameworks"] = sorted(list(target_frameworks))

    if project_files:
        result["project_files"] = project_data

    if solution_files:
        result["solution_files"] = solution_files

    result["global_json_exists"] = global_json_exists
    result["directory_build_props_exists"] = directory_build_props_exists
    result["packages_lock_exists"] = packages_lock_exists

    if test_projects:
        result["test_projects"] = test_projects

print(json.dumps(result, indent=2))
EOF