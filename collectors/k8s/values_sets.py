"""Works out which values sets the helm sub-collector renders a chart with.

Usage: values_sets.py <chart-dir>, with the helm_values and helm_values_chains
inputs in HELM_VALUES and HELM_VALUES_CHAINS. Prints
{"sets": [[file, ...], ...], "validated_only": bool}: each set lists the
values files applied in order, starting with the chart's values.yaml. A chart
no set applies to gets its values.yaml alone, marked validated_only.
"""

import glob
import itertools
import json
import os
import sys

GLOB_CHARS = set("*?[")


def from_helm_values(chart_dir, text):
    """One set per line, or per match of a glob; a chart skips a line whose files it doesn't have."""
    sets = []
    for raw in text.splitlines():
        tokens = raw.split("#", 1)[0].split()
        if not tokens:
            continue
        choices = []
        for token in tokens:
            if GLOB_CHARS & set(token):
                matches = sorted(os.path.relpath(m, chart_dir)
                                 for m in glob.glob(os.path.join(chart_dir, token)) if os.path.isfile(m))
            else:
                matches = [os.path.normpath(token)] if os.path.isfile(os.path.join(chart_dir, token)) else []
            if not matches:
                break
            choices.append(matches)
        else:
            sets.extend(list(files) for files in itertools.product(*choices))
    return sets


def chains(chart_dir, mode):
    """Port of the chain rule a CI that applies overlays by file name uses:
    every values-*.yaml that no other overlay extends (continues at a dash)
    is a chain of values.yaml, the overlays it extends, then itself."""
    if not os.path.isfile(os.path.join(chart_dir, "values.yaml")):
        return []
    names = sorted(n for n in os.listdir(chart_dir)
                   if n.startswith("values-") and n.endswith(".yaml") and os.path.isfile(os.path.join(chart_dir, n)))
    stems = [n[:-len(".yaml")] for n in names]
    leaves = [n for n, stem in zip(names, stems) if not any(o.startswith(stem + "-") for o in stems)]
    if not leaves:
        return [["values.yaml"]] if mode == "all" else []
    result = set()
    for leaf in leaves:
        chain, suffix = ["values.yaml"], ""
        for segment in leaf[len("values-"):-len(".yaml")].split("-"):
            suffix = f"{suffix}-{segment}" if suffix else segment
            if os.path.isfile(os.path.join(chart_dir, f"values-{suffix}.yaml")):
                chain.append(f"values-{suffix}.yaml")
        result.add(tuple(chain))
    return [list(c) for c in sorted(result)]


def main():
    chart_dir = sys.argv[1]
    mode = os.environ.get("HELM_VALUES_CHAINS", "").strip().lower()
    if mode not in ("", "overlays", "all"):
        sys.exit(f"helm_values_chains must be 'overlays', 'all' or empty, got {mode!r}")

    has_defaults = os.path.isfile(os.path.join(chart_dir, "values.yaml"))
    sets, seen = [], set()
    candidates = from_helm_values(chart_dir, os.environ.get("HELM_VALUES", ""))
    if mode:
        candidates += chains(chart_dir, mode)
    for files in candidates:
        # values.yaml always applies first, as helm applies it itself.
        files = [f for f in files if f != "values.yaml"]
        files = (["values.yaml"] if has_defaults else []) + files
        if tuple(files) not in seen:
            seen.add(tuple(files))
            sets.append(files)

    if sets:
        print(json.dumps({"sets": sets, "validated_only": False}))
    else:
        print(json.dumps({"sets": [["values.yaml"] if has_defaults else []], "validated_only": True}))


if __name__ == "__main__":
    main()
