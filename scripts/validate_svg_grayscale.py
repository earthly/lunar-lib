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


def is_allowed_fill(value):
    """Check if a fill value is allowed (white, black, none, currentColor, or url ref)."""
    v = value.strip().lower()
    return v in {"white", "black", "none", "currentcolor", "#fff", "#ffffff", "#000", "#000000"} or v.startswith("url(")


def is_allowed_stop_color(value):
    """Check if a gradient stop-color is allowed (must be white)."""
    v = value.strip().lower()
    return v in {"white", "#fff", "#ffffff"}


def validate_svg(path):
    with open(path) as f:
        content = f.read()

    errors = []

    # Match fill values in both style attributes (fill:X) and XML attributes (fill="X")
    fill_values = re.findall(r'(?i)\bfill\s*[:=]\s*["\']?([^;"\'\s>]+)', content)
    for value in set(fill_values):
        if not is_allowed_fill(value):
            errors.append(f"  Non-grayscale fill found: {value}")

    # Match stop-color values in both style and XML attributes
    stop_values = re.findall(r'(?i)\bstop-color\s*[:=]\s*["\']?([^;"\'\s>]+)', content)
    for value in set(stop_values):
        if not is_allowed_stop_color(value):
            errors.append(f"  Non-grayscale gradient stop: {value}")

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
