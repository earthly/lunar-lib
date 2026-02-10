#!/usr/bin/env python3
"""Validate that SVG icon assets use grayscale-via-alpha only.

All SVG fills must be either:
  - fill:white with a fill-opacity value
  - fill:url(#...) referencing a gradient (whose stops must be white+opacity)
  - fill:black or fill:none

No rgb() colors are allowed — they get flattened to white on the website.
"""

import glob
import re
import sys


def validate_svg(path):
    with open(path) as f:
        content = f.read()

    errors = []

    # Check for rgb() in fill: properties
    rgb_fills = re.findall(r"fill:rgb\(\d+,\s*\d+,\s*\d+\)", content)
    if rgb_fills:
        for fill in set(rgb_fills):
            errors.append(f"  Non-grayscale fill found: {fill}")

    # Check for rgb() in gradient stop-color: properties
    rgb_stops = re.findall(r"stop-color:rgb\(\d+,\s*\d+,\s*\d+\)", content)
    if rgb_stops:
        for stop in set(rgb_stops):
            errors.append(f"  Non-grayscale gradient stop: {stop}")

    return errors


def main():
    svg_files = sorted(
        glob.glob("collectors/*/assets/*.svg")
        + glob.glob("policies/*/assets/*.svg")
        + glob.glob("catalogers/*/assets/*.svg")
    )

    if not svg_files:
        print("No SVG assets found.")
        return 0

    failed = False
    for path in svg_files:
        errors = validate_svg(path)
        if errors:
            failed = True
            print(f"FAIL: {path}")
            for e in errors:
                print(e)
            print(f"  Hint: run 'python scripts/svg_to_grayscale.py {path}' to fix")
            print()

    if failed:
        print("SVG grayscale validation failed.")
        print("All icon SVGs must use fill:white with fill-opacity for grayscale.")
        print("RGB colors get flattened to white on the website.")
        return 1

    print(f"OK: {len(svg_files)} SVG(s) validated — all grayscale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
