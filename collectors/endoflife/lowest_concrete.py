#!/usr/bin/env python3
"""
Pick the lowest concrete version that satisfies a version constraint.

The endoflife collector reads pinned-version expressions from various
ecosystem files (package.json engines.node, pyproject.toml
requires-python, composer.json require.php). Those values may be a
single version, a range, or a set of alternatives separated by `||`.
The "worst case" version a runtime can drop to is the lowest concrete
satisfier — that's what we want to check against EOL data.

Heuristic:
  - Split on ``||`` (alternatives — pick the lowest result of each).
  - For each alternative, find the leftmost ``digits[.digits[...]]``
    sequence and use it as the satisfying version.
  - Strip a leading ``v`` and any leading non-numeric prefix.

Worked examples:
  ">=3.10"            -> 3.10
  ">=3.10,<4"         -> 3.10
  "^20.0.0"           -> 20.0.0
  "^7.4 || ^8.1"      -> 7.4
  "v18.0.0"           -> 18.0.0
"""
import re
import sys

VERSION_RE = re.compile(r"(\d+(?:\.\d+)*)")


def parse_alternative(expr: str) -> str:
    expr = expr.strip().lstrip("v")
    m = VERSION_RE.search(expr)
    return m.group(1) if m else ""


def parse(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if "||" in raw:
        candidates = [parse_alternative(part) for part in raw.split("||")]
        candidates = [c for c in candidates if c]
        if not candidates:
            return ""
        return min(candidates, key=lambda v: tuple(int(p) for p in v.split(".")))
    return parse_alternative(raw)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(0)
    out = parse(sys.argv[1])
    if out:
        sys.stdout.write(out)
