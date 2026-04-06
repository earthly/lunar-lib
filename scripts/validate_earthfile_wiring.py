#!/usr/bin/env python3
"""
Validate that all plugin Earthfiles with an `image:` target are wired into the
root Earthfile's `+all` target.

Any collector, policy, or cataloger that defines an `image:` target needs a
corresponding `BUILD --pass-args ./<type>/<name>+image` line in the root
Earthfile's `+all` target — otherwise CI will never build or push that image.

Usage:
    python scripts/validate_earthfile_wiring.py
"""

import re
import sys
from pathlib import Path

PLUGIN_DIRS = ["collectors", "policies", "catalogers"]


def find_earthfiles_with_image_target(base_dir: Path) -> list[str]:
    """Find all plugin Earthfiles that define an `image:` target.

    Returns paths like './collectors/gitleaks+image'.
    """
    results = []
    for plugin_dir in PLUGIN_DIRS:
        dir_path = base_dir / plugin_dir
        if not dir_path.exists():
            continue
        for earthfile in sorted(dir_path.glob("*/Earthfile")):
            content = earthfile.read_text()
            if re.search(r"^image:\s*$", content, re.MULTILINE):
                plugin_name = earthfile.parent.name
                results.append(f"./{plugin_dir}/{plugin_name}+image")
    return results


def parse_all_target_refs(earthfile_path: Path) -> set[str]:
    """Parse the root Earthfile's `+all` target for BUILD --pass-args refs."""
    content = earthfile_path.read_text()
    refs = set()

    in_all = False
    for line in content.splitlines():
        # Detect start of all: target
        if re.match(r"^all:\s*$", line):
            in_all = True
            continue
        # Detect start of another target (end of all:)
        if in_all and re.match(r"^\S+.*:\s*$", line) and not line.startswith(" "):
            break
        if in_all:
            match = re.match(r"\s+BUILD\s+--pass-args\s+(\S+)", line)
            if match:
                refs.add(match.group(1))

    return refs


def main():
    base_dir = Path(__file__).parent.parent
    root_earthfile = base_dir / "Earthfile"

    if not root_earthfile.exists():
        print("ERROR: Root Earthfile not found")
        sys.exit(1)

    earthfiles_with_image = find_earthfiles_with_image_target(base_dir)
    all_refs = parse_all_target_refs(root_earthfile)

    missing = [ef for ef in earthfiles_with_image if ef not in all_refs]

    print(f"Found {len(earthfiles_with_image)} plugin(s) with image: target")
    print(f"Found {len(all_refs)} BUILD --pass-args refs in +all target")

    if missing:
        print(f"\nERROR: {len(missing)} plugin image(s) NOT wired into +all:")
        for ref in missing:
            print(f"  - {ref}")
        print("\nFix: Add these lines to the +all target in the root Earthfile:")
        for ref in missing:
            print(f"    BUILD --pass-args {ref}")
        sys.exit(1)

    print("\nAll plugin images are wired into the +all target.")
    sys.exit(0)


if __name__ == "__main__":
    main()
