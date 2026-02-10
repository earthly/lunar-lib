#!/usr/bin/env python3
"""Convert an SVG's colors to grayscale via the alpha channel.

Maps each RGB fill/stop-color to white with fill-opacity based on luminance.
Also removes background/shadow silhouette layers (large white shapes) that
would otherwise composite with detail shapes and wash out the grayscale.

Usage:
    python scripts/svg_to_grayscale.py <input.svg> [output.svg]

If output is omitted, the input file is overwritten in-place.
"""

import re
import sys


def luminance(r, g, b):
    """Standard luminance: L = 0.2126*R + 0.7152*G + 0.0722*B"""
    return 0.2126 * (r / 255) + 0.7152 * (g / 255) + 0.0722 * (b / 255)


def process_svg(input_path, output_path):
    with open(input_path, "r") as f:
        svg = f.read()

    # Collect original colors for summary
    colors_found = set()
    for m in re.finditer(r"fill:rgb\((\d+),(\d+),(\d+)\)", svg):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        colors_found.add((r, g, b, round(luminance(r, g, b), 2)))

    # Identify large white silhouette/shadow paths (path data > 5000 chars)
    # These overlap the entire icon and wash out alpha-based grayscale detail.
    # We remove all but one and make the survivor low-opacity as a subtle outline.
    silhouette_count = 0

    def replace_path(match):
        nonlocal silhouette_count
        path_data = match.group(1)
        style = match.group(2)

        # Check if this is a large white silhouette path
        is_white = "fill:white" in style and "fill:rgb" not in style
        is_large = len(path_data) > 5000
        has_url = "fill:url" in style

        if is_white and is_large and not has_url:
            silhouette_count += 1
            if silhouette_count == 1:
                # Keep one silhouette as a faint outline
                new_style = style.replace("fill:white", "fill:white;fill-opacity:0.15")
                return f'<path d="{path_data}" style="{new_style}"/>'
            else:
                # Remove duplicate silhouettes
                return ""

        # Convert fill:rgb(R,G,B) to fill:white;fill-opacity:L
        rgb_match = re.search(r"fill:rgb\((\d+),(\d+),(\d+)\)", style)
        if rgb_match:
            r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
            opacity = round(luminance(r, g, b), 2)
            new_style = re.sub(
                r"fill:rgb\(\d+,\d+,\d+\)",
                f"fill:white;fill-opacity:{opacity}",
                style,
            )
            return f'<path d="{path_data}" style="{new_style}"/>'

        # For small white paths (detail highlights), keep as-is with opacity 1
        if is_white:
            if "fill-opacity" not in style:
                new_style = style.replace("fill:white", "fill:white;fill-opacity:1")
            else:
                new_style = style
            return f'<path d="{path_data}" style="{new_style}"/>'

        return match.group(0)

    svg = re.sub(r'<path d="([^"]+)" style="([^"]+)"/>', replace_path, svg)

    # Convert gradient stop colors to white+opacity
    def replace_gradient_stop(match):
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        opacity = round(luminance(r, g, b), 2)
        return f"stop-color:white;stop-opacity:{opacity}"

    svg = re.sub(
        r'stop-color:rgb\((\d+),(\d+),(\d+)\);stop-opacity:[^"]*',
        replace_gradient_stop,
        svg,
    )

    # Clean up empty lines from removed paths
    svg = re.sub(r"\n\s*\n", "\n", svg)

    with open(output_path, "w") as f:
        f.write(svg)

    print(f"Converted {input_path} -> {output_path}")
    print(f"  Silhouettes found: {silhouette_count} (kept 1 at 0.15 opacity, removed {silhouette_count - 1})")
    print("\nColor -> Alpha mapping:")
    for r, g, b, op in sorted(colors_found, key=lambda x: -x[3]):
        print(f"  rgb({r},{g},{b}) -> fill:white; fill-opacity:{op}")
    print("  white (small details) -> fill:white; fill-opacity:1")
    print("  white (silhouette) -> fill:white; fill-opacity:0.15")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.svg> [output.svg]", file=sys.stderr)
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file
    process_svg(input_file, output_file)
