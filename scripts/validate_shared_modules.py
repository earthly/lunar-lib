#!/usr/bin/env python3
"""Require every copy of a shared policy module to be identical.

The hub packages only a plugin's own directory, so a module that several
policies use is copied into each of them. This fails when the copies differ,
so a fix made in one copy can't silently miss the others.

Usage:
    python scripts/validate_shared_modules.py
"""

import sys
from pathlib import Path

SHARED = ["version_minimum.py", "rerun_hint.py"]


def main():
    root = Path(__file__).resolve().parent.parent
    failed = False
    for name in SHARED:
        copies = sorted(p for p in (root / "policies").rglob(name) if ".venv" not in p.parts)
        if len(copies) < 2:
            print(f"✗ {name}: expected copies in several policies, found {len(copies)}")
            failed = True
            continue
        variants = {}
        for path in copies:
            variants.setdefault(path.read_bytes(), []).append(path.relative_to(root))
        if len(variants) == 1:
            print(f"✓ {name}: {len(copies)} identical copies")
            continue
        failed = True
        print(f"✗ {name}: {len(copies)} copies in {len(variants)} versions; copy your change to all of them:")
        for paths in sorted(variants.values(), key=len, reverse=True):
            print("    " + ", ".join(str(p) for p in paths))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
