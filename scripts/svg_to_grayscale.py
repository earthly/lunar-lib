#!/usr/bin/env python3
"""Convert an SVG's colors to grayscale via the alpha channel.

Handles:
  - fill:rgb(R,G,B) in inline styles
  - fill="#RRGGBB" / fill="#RGB" in XML attributes
  - stop-color in gradient definitions
  - Large white silhouette layers (removed/reduced)

Usage:
    python scripts/svg_to_grayscale.py <input.svg> [output.svg]

If output is omitted, the input file is overwritten in-place.
"""

import re
import sys


def luminance(r, g, b):
    """Standard luminance: L = 0.2126*R + 0.7152*G + 0.0722*B"""
    return 0.2126 * (r / 255) + 0.7152 * (g / 255) + 0.0722 * (b / 255)


def hex_to_rgb(hex_str):
    """Convert #RGB or #RRGGBB to (r, g, b) tuple."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def process_svg(input_path, output_path):
    with open(input_path, "r") as f:
        svg = f.read()

    colors_found = set()

    # Collect rgb() colors
    for m in re.finditer(r"fill:rgb\((\d+),\s*(\d+),\s*(\d+)\)", svg):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        colors_found.add((r, g, b))

    # Collect hex colors from style (fill:#xxx) and attributes (fill="#xxx")
    for m in re.finditer(r'fill[=:]\s*"?(#[0-9a-fA-F]{3,6})\b', svg):
        r, g, b = hex_to_rgb(m.group(1))
        colors_found.add((r, g, b))

    # --- Silhouette removal (large white paths) ---
    silhouette_count = 0

    def replace_path(match):
        nonlocal silhouette_count
        path_data = match.group(1)
        style = match.group(2)

        is_white = "fill:white" in style and "fill:rgb" not in style
        is_large = len(path_data) > 5000
        has_url = "fill:url" in style

        if is_white and is_large and not has_url:
            silhouette_count += 1
            if silhouette_count == 1:
                new_style = style.replace("fill:white", "fill:white;fill-opacity:0.15")
                return f'<path d="{path_data}" style="{new_style}"/>'
            else:
                return ""

        # Convert fill:rgb(R,G,B) to fill:white;fill-opacity:L
        rgb_match = re.search(r"fill:rgb\((\d+),\s*(\d+),\s*(\d+)\)", style)
        if rgb_match:
            r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
            opacity = round(luminance(r, g, b), 2)
            new_style = re.sub(
                r"fill:rgb\(\d+,\s*\d+,\s*\d+\)",
                f"fill:white;fill-opacity:{opacity}",
                style,
            )
            return f'<path d="{path_data}" style="{new_style}"/>'

        if is_white and "fill-opacity" not in style:
            new_style = style.replace("fill:white", "fill:white;fill-opacity:1")
            return f'<path d="{path_data}" style="{new_style}"/>'

        return match.group(0)

    svg = re.sub(r'<path d="([^"]+)" style="([^"]+)"/>', replace_path, svg)

    # --- Convert hex fills in style attributes: fill:#RRGGBB ---
    def replace_hex_fill_style(match):
        hex_color = match.group(1)
        r, g, b = hex_to_rgb(hex_color)
        opacity = round(luminance(r, g, b), 2)
        return f"fill:white;fill-opacity:{opacity}"

    svg = re.sub(r"fill:(#[0-9a-fA-F]{3,6})\b", replace_hex_fill_style, svg)

    # --- Convert hex fills in XML attributes: fill="#RRGGBB" ---
    def replace_hex_fill_attr(match):
        hex_color = match.group(1)
        r, g, b = hex_to_rgb(hex_color)
        opacity = round(luminance(r, g, b), 2)
        return f'fill="white" fill-opacity="{opacity}"'

    svg = re.sub(r'fill="(#[0-9a-fA-F]{3,6})"', replace_hex_fill_attr, svg)

    # --- Convert gradient stop colors ---
    def replace_gradient_stop_style(match):
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        opacity = round(luminance(r, g, b), 2)
        return f"stop-color:white;stop-opacity:{opacity}"

    svg = re.sub(
        r'stop-color:rgb\((\d+),\s*(\d+),\s*(\d+)\);stop-opacity:[^"]*',
        replace_gradient_stop_style,
        svg,
    )

    # Clean up empty lines from removed paths
    svg = re.sub(r"\n\s*\n", "\n", svg)

    with open(output_path, "w") as f:
        f.write(svg)

    print(f"Converted {input_path} -> {output_path}")
    if silhouette_count > 0:
        kept = min(silhouette_count, 1)
        removed = silhouette_count - kept
        print(f"  Silhouettes: kept {kept} at 0.15 opacity, removed {removed}")
    print("\nColor -> Alpha mapping:")
    for r, g, b in sorted(colors_found, key=lambda c: -luminance(*c)):
        op = round(luminance(r, g, b), 2)
        print(f"  rgb({r},{g},{b}) -> fill:white; fill-opacity:{op}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.svg> [output.svg]", file=sys.stderr)
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file
    process_svg(input_file, output_file)
