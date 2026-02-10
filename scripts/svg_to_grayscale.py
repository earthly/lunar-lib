#!/usr/bin/env python3
"""Convert an SVG's colors to grayscale via the alpha channel.

Maps each RGB fill/stop-color to white with fill-opacity based on luminance.
This ensures icons survive color flattening (where all fills become white)
by encoding grayscale information in the alpha channel.

Usage:
    python scripts/svg_to_grayscale.py <input.svg> [output.svg]

If output is omitted, the input file is overwritten in-place.
"""

import re
import sys


def luminance(r, g, b):
    """Standard luminance: L = 0.2126*R + 0.7152*G + 0.0722*B"""
    return 0.2126 * (r / 255) + 0.7152 * (g / 255) + 0.0722 * (b / 255)


def replace_rgb_fill(match):
    """Replace fill:rgb(R,G,B) with fill:white;fill-opacity:L"""
    r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
    opacity = round(luminance(r, g, b), 2)
    return f"fill:white;fill-opacity:{opacity}"


def replace_gradient_stop(match):
    """Replace stop-color:rgb(R,G,B);stop-opacity:N with white+opacity."""
    r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
    opacity = round(luminance(r, g, b), 2)
    return f"stop-color:white;stop-opacity:{opacity}"


def replace_fill_white(match):
    """Ensure fill:white gets explicit fill-opacity:1."""
    return "fill:white;fill-opacity:1"


def process_svg(input_path, output_path):
    with open(input_path, "r") as f:
        svg = f.read()

    # Collect original colors for summary
    colors_found = set()
    for m in re.finditer(r"fill:rgb\((\d+),(\d+),(\d+)\)", svg):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        colors_found.add((r, g, b, round(luminance(r, g, b), 2)))

    # Replace fill:rgb(R,G,B) with fill:white;fill-opacity:L
    svg = re.sub(r"fill:rgb\((\d+),(\d+),(\d+)\)", replace_rgb_fill, svg)

    # Replace stop-color:rgb(R,G,B);stop-opacity:N in gradient stops
    svg = re.sub(
        r'stop-color:rgb\((\d+),(\d+),(\d+)\);stop-opacity:[^"]*',
        replace_gradient_stop,
        svg,
    )

    # Add fill-opacity:1 to existing fill:white (where not already set)
    svg = re.sub(r"fill:white(?!;fill-opacity)", replace_fill_white, svg)

    with open(output_path, "w") as f:
        f.write(svg)

    print(f"Converted {input_path} -> {output_path}")
    print("\nColor -> Alpha mapping:")
    for r, g, b, op in sorted(colors_found, key=lambda x: -x[3]):
        print(f"  rgb({r},{g},{b}) -> fill:white; fill-opacity:{op}")
    if "fill:white" in svg:
        print("  white -> fill:white; fill-opacity:1")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.svg> [output.svg]", file=sys.stderr)
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file
    process_svg(input_file, output_file)
