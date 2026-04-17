#!/usr/bin/env python3
"""Parse Renovate config from JSON / JSON5 / .renovaterc / package.json (renovate key).

Outputs parsed JSON to stdout. Exits 2 if file has no renovate config (package.json
without a "renovate" key). Exits 1 if parsing fails entirely.
"""
import json
import re
import sys


def strip_json5_extras(text):
    # Remove // line comments (not inside strings — approximated)
    text = re.sub(r"(^|[^:])//[^\n]*", r"\1", text)
    # Remove /* ... */ block comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Remove trailing commas before } or ]
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def parse_content(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(strip_json5_extras(text))


def main():
    if len(sys.argv) != 2:
        print("usage: parse_renovate.py <path>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    data = parse_content(text)

    # package.json: extract the "renovate" key; absence → not a renovate config
    if path.endswith("package.json"):
        if not isinstance(data, dict) or "renovate" not in data:
            sys.exit(2)
        data = data["renovate"]

    json.dump(data, sys.stdout)


if __name__ == "__main__":
    main()
