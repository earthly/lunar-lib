#!/usr/bin/env python3
"""Convert an SVG's colors to grayscale.

Maps each RGB fill/stop-color to a grayscale value based on luminance,
so icons render with proper contrast on dark backgrounds.

Usage:
    python scripts/svg_to_grayscale.py <input.svg> [output.svg]

If output is omitted, the input file is overwritten in-place.
"""

import re
import sys


def luminance(r, g, b):
    """Standard luminance: L = 0.2126*R + 0.7152*G + 0.0722*B"""
    return 0.2126 * (r / 255) + 0.7152 * (g / 255) + 0.0722 * (b / 255)


def gray_value(r, g, b):
    """Map color luminance to grayscale 0-255."""
    return round(luminance(r, g, b) * 255)


def replace_rgb_fill(match):
    r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
    g_val = gray_value(r, g, b)
    return f"fill:rgb({g_val},{g_val},{g_val})"


def replace_gradient_stop(match):
    r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
    g_val = gray_value(r, g, b)
    return f"stop-color:rgb({g_val},{g_val},{g_val});stop-opacity:1"


def process_svg(input_path, output_path):
    with open(input_path, "r") as f:
        svg = f.read()

    # Collect original colors for summary
    colors_found = set()
    for m in re.finditer(r"fill:rgb\((\d+),(\d+),(\d+)\)", svg):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        colors_found.add((r, g, b, gray_value(r, g, b)))

    # Replace fill:rgb(R,G,B) with fill:rgb(G,G,G)
    svg = re.sub(r"fill:rgb\((\d+),(\d+),(\d+)\)", replace_rgb_fill, svg)

    # Replace stop-color:rgb(R,G,B);stop-opacity:N in gradient stops
    svg = re.sub(
        r"stop-color:rgb\((\d+),(\d+),(\d+)\);stop-opacity:[^\"]*",
        replace_gradient_stop,
        svg,
    )

    # Clean up any fill-opacity from previous white+alpha conversions
    svg = re.sub(r";fill-opacity:[0-9.]+", "", svg)

    with open(output_path, "w") as f:
        f.write(svg)

    print(f"Converted {input_path} -> {output_path}")
    print("\nColor -> Grayscale mapping:")
    for r, g, b, gv in sorted(colors_found, key=lambda x: -x[3]):
        print(f"  rgb({r},{g},{b}) -> rgb({gv},{gv},{gv})")
    if "fill:white" in svg:
        print("  white -> white (unchanged)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.svg> [output.svg]", file=sys.stderr)
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file
    process_svg(input_file, output_file)
