#!/usr/bin/env python3
"""
Normalize an endoflife.date cycle object into the .lang.<lang>.eol shape.

endoflife.date returns either booleans OR ISO date strings for the
``eol``, ``support``, and ``lts`` fields, and some products omit
``support`` entirely. This helper takes a raw cycle JSON on stdin plus
metadata via env, and emits the normalized eol object on stdout.

Inputs (env): NOW, TODAY, PRODUCT, DETECTED_VERSION
Stdin: raw cycle JSON object (one object, the matched cycle).
Stdout: normalized eol JSON object.
"""
import json
import os
import sys


def _date_only(v):
    return v if isinstance(v, str) and len(v) >= 10 else None


def main():
    cycle = json.load(sys.stdin)
    today = os.environ["TODAY"]
    now = os.environ["NOW"]
    product = os.environ["PRODUCT"]
    detected = os.environ["DETECTED_VERSION"]

    eol_raw = cycle.get("eol")
    support_raw = cycle.get("support")
    lts_raw = cycle.get("lts")

    if isinstance(eol_raw, bool):
        is_eol = eol_raw
    elif isinstance(eol_raw, str):
        is_eol = eol_raw <= today
    else:
        is_eol = False

    if is_eol:
        is_supported = False
    elif isinstance(support_raw, bool):
        is_supported = support_raw
    elif isinstance(support_raw, str):
        is_supported = support_raw > today
    else:
        is_supported = not is_eol

    if isinstance(lts_raw, bool):
        is_lts = lts_raw
    elif isinstance(lts_raw, str):
        is_lts = True
    else:
        is_lts = False

    out = {
        "source": {
            "tool": "endoflife.date",
            "integration": "api",
            "collected_at": now,
        },
        "product": product,
        "cycle": str(cycle.get("cycle", "")),
        "detected_version": detected,
        "is_eol": is_eol,
        "is_supported": is_supported,
        "eol_date": _date_only(eol_raw),
        "support_until": _date_only(support_raw),
        "lts": is_lts,
        "latest_in_cycle": cycle.get("latest"),
    }
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
