#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a .NET project
if ! is_dotnet_project; then
    echo "No .NET project detected, exiting"
    exit 0
fi

# Use Python for robust XML parsing of .csproj/.fsproj/.vbproj files
python3 - <<'PY' | lunar collect -j ".lang.dotnet" -
import json
import os
import xml.etree.ElementTree as ET

MSBUILD_NS = "{http://schemas.microsoft.com/developer/msbuild/2003}"

TEST_PACKAGES = {
    "xunit": "xunit",
    "xunit.core": "xunit",
    "xunit.runner.visualstudio": "xunit",
    "nunit": "nunit",
    "nunit3testadapter": "nunit",
    "mstest.testadapter": "mstest",
    "mstest.testframework": "mstest",
}


def find_element(root, tag):
    """Find element with or without MSBuild namespace."""
    el = root.find(f".//{tag}")
    if el is None:
        el = root.find(f".//{MSBUILD_NS}{tag}")
    return el


def find_all_elements(root, tag):
    """Find all elements with or without MSBuild namespace."""
    elements = root.findall(f".//{tag}")
    elements.extend(root.findall(f".//{MSBUILD_NS}{tag}"))
    return elements


def parse_project_file(path):
    """Parse a .NET project file and extract metadata."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception:
        return None

    # Determine file type
    ext = os.path.splitext(path)[1].lower()
    type_map = {".csproj": "csharp", ".fsproj": "fsharp", ".vbproj": "vbnet"}
    file_type = type_map.get(ext, "unknown")

    # Extract target framework(s)
    target_framework = ""
    tf_elem = find_element(root, "TargetFramework")
    if tf_elem is not None and tf_elem.text:
        target_framework = tf_elem.text.strip()

    target_frameworks = []
    tfs_elem = find_element(root, "TargetFrameworks")
    if tfs_elem is not None and tfs_elem.text:
        target_frameworks = [f.strip() for f in tfs_elem.text.strip().split(";") if f.strip()]
    elif target_framework:
        target_frameworks = [target_framework]

    # Extract output type
    output_type = ""
    ot_elem = find_element(root, "OutputType")
    if ot_elem is not None and ot_elem.text:
        output_type = ot_elem.text.strip()

    # Detect test project
    is_test = False
    test_framework = ""

    itp_elem = find_element(root, "IsTestProject")
    if itp_elem is not None and itp_elem.text and itp_elem.text.strip().lower() == "true":
        is_test = True

    # Check PackageReference for test frameworks
    for pr in find_all_elements(root, "PackageReference"):
        include = pr.get("Include", "") or pr.get("include", "")
        key = include.lower()
        if key in TEST_PACKAGES:
            is_test = True
            if not test_framework:
                test_framework = TEST_PACKAGES[key]

    # Microsoft.NET.Test.Sdk is a strong signal
    for pr in find_all_elements(root, "PackageReference"):
        include = pr.get("Include", "") or pr.get("include", "")
        if include.lower() == "microsoft.net.test.sdk":
            is_test = True
            break

    info = {
        "path": path,
        "type": file_type,
        "target_framework": target_framework or (target_frameworks[0] if target_frameworks else ""),
    }
    if output_type:
        info["output_type"] = output_type

    return info, target_frameworks, is_test, test_framework


def main():
    # Find all project files
    project_files = []
    for root_dir, dirs, files in os.walk("."):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith((".csproj", ".fsproj", ".vbproj")):
                path = os.path.join(root_dir, f)
                # Normalize path (remove ./ prefix)
                if path.startswith("./"):
                    path = path[2:]
                project_files.append(path)

    if not project_files:
        # No project files found — nothing to collect
        return

    all_project_info = []
    all_target_frameworks = set()
    test_projects = []

    for pf in project_files:
        result = parse_project_file(pf)
        if result is None:
            continue

        info, frameworks, is_test, test_framework = result
        all_project_info.append(info)
        all_target_frameworks.update(frameworks)

        if is_test:
            test_entry = {"path": pf, "type": info["type"]}
            if test_framework:
                test_entry["test_framework"] = test_framework
            test_projects.append(test_entry)

    # Find solution files
    solution_files = []
    for f in os.listdir("."):
        if f.endswith(".sln"):
            solution_files.append(f)

    # Check global.json for SDK version
    sdk_version = ""
    global_json_exists = os.path.isfile("global.json")
    if global_json_exists:
        try:
            with open("global.json") as gj:
                gj_data = json.load(gj)
            sdk_version = gj_data.get("sdk", {}).get("version", "")
        except Exception:
            pass

    # Check other files
    directory_build_props_exists = os.path.isfile("Directory.Build.props")

    # Check for packages.lock.json anywhere in the project
    packages_lock_exists = False
    for root_dir, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if "packages.lock.json" in files:
            packages_lock_exists = True
            break

    # Build output
    output = {
        "project_files": all_project_info,
        "target_frameworks": sorted(all_target_frameworks),
        "solution_files": sorted(solution_files),
        "global_json_exists": global_json_exists,
        "directory_build_props_exists": directory_build_props_exists,
        "packages_lock_exists": packages_lock_exists,
        "test_projects": test_projects,
        "source": {"tool": "dotnet", "integration": "code"},
    }

    if sdk_version:
        output["sdk_version"] = sdk_version

    print(json.dumps(output))


main()
PY
