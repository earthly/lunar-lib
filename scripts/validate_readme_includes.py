#!/usr/bin/env python3
"""Require `include:` on every lunar-lib import shown in the docs.

A plugin imported without `include:` runs every sub-collector, check, cataloger
or probe it has, including the ones a later version adds. A user who copies a
whole-plugin snippet from a README takes on those changes at every bump without
choosing them. This scans the YAML code blocks of the plugin READMEs and
ai-context/, and fails when a `uses: github://earthly/lunar-lib/...` entry

- has no `include:`, or an empty one,
- uses `exclude:` instead, or
- includes a name its plugin's manifest doesn't define. The hub doesn't check
  these names either, so a typo runs nothing without any error.

Usage:
    python scripts/validate_readme_includes.py [--self-test]
"""

import glob
import re
import sys
import textwrap
from pathlib import Path

import yaml

DOC_GLOBS = [
    "collectors/**/*.md",
    "policies/**/*.md",
    "catalogers/**/*.md",
    "probes/**/*.md",
    "ai-context/**/*.md",
]
MANIFESTS = {
    "collectors": "lunar-collector.yml",
    "policies": "lunar-policy.yml",
    "catalogers": "lunar-cataloger.yml",
    "probes": "lunar-probe.yml",
}
FENCE = re.compile(r"^\s*```\s*(\S*)")
LIB_USES = re.compile(
    r"(?:github://)?earthly/lunar-lib/(collectors|policies|catalogers|probes)/([^@\s]+)"
)


def manifest_items(kind, name):
    """Names a plugin's manifest defines, or None when there is no such plugin."""
    path = Path(kind) / name / MANIFESTS[kind]
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text()) or {}
    return [item.get("name") for item in data.get(kind) or []]


def yaml_blocks(text):
    """Yield (first line number, source) for each YAML code block in markdown."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m:
            i += 1
            continue
        start = i + 1
        i += 1
        while i < len(lines) and not FENCE.match(lines[i]):
            i += 1
        if m.group(1) in ("yaml", "yml", ""):
            yield start + 1, textwrap.dedent("\n".join(lines[start:i]))
        i += 1


def imports(node):
    """Yield every mapping node that has a `uses:` key, at any depth."""
    if isinstance(node, yaml.MappingNode):
        if any(isinstance(k, yaml.ScalarNode) and k.value == "uses" for k, _ in node.value):
            yield node
        for _, value in node.value:
            yield from imports(value)
    elif isinstance(node, yaml.SequenceNode):
        for value in node.value:
            yield from imports(value)


def check_entry(node, items_for):
    """Return (line offset, kind/name, problem) for one import, or None if it's fine."""
    keys = {k.value: v for k, v in node.value if isinstance(k, yaml.ScalarNode)}
    uses = keys["uses"]
    m = LIB_USES.search(uses.value) if isinstance(uses, yaml.ScalarNode) else None
    if not m:
        return None
    kind, name = m.group(1), m.group(2)
    where = (node.start_mark.line, f"{kind}/{name}")
    if "exclude" in keys:
        return *where, "uses `exclude:`; list what to run with `include:` instead"
    include = keys.get("include")
    if include is None:
        return *where, "has no `include:`; list the sub-collectors or checks to run"
    names = [n.value for n in include.value] if isinstance(include, yaml.SequenceNode) else []
    if not names or not all(isinstance(n, yaml.ScalarNode) for n in include.value):
        return *where, "`include:` must be a non-empty list of names"
    if "{" in name:  # a template placeholder, not a real plugin
        return None
    known = items_for(kind, name)
    if known is None:
        return *where, "no such plugin in this repository"
    unknown = [n for n in names if n not in known]
    if unknown:
        return *where, f"`include:` names {unknown} aren't in its manifest: {known}"
    return None


def check_markdown(text, path, items_for):
    errors = []
    for first_line, source in yaml_blocks(text):
        if "earthly/lunar-lib/" not in source or "uses:" not in source:
            continue
        try:
            docs = list(yaml.compose_all(source))
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            line = first_line + (mark.line if mark else 0)
            errors.append(f"{path}:{line}: YAML block with a lunar-lib import doesn't parse: {e}")
            continue
        for doc in docs:
            for node in imports(doc):
                problem = check_entry(node, items_for)
                if problem:
                    offset, plugin, message = problem
                    errors.append(f"{path}:{first_line + offset}: {plugin} {message}")
    return errors


SELF_TEST_ITEMS = {("collectors", "k8s"): ["k8s", "helm", "cicd"], ("policies", "k8s"): ["valid", "pdb"]}

SELF_TEST_GOOD = """
```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/k8s@v1.0.0
    include:
      - k8s   # Plain manifests
      - helm  # Helm charts, rendered
  - name: second
    uses: "github://earthly/lunar-lib/collectors/k8s@main"
    include: [cicd]
policies:
  - uses: github://earthly/lunar-lib/policies/{path-to-policy}@v1.0.0
    include: [example-check]
  - uses: ./policies/local
  - uses: github://acme/plugins/policies/k8s@v1
```

   ```yaml
   policies:
     - uses: github://earthly/lunar-lib/policies/k8s@v1.0.0
       include: [valid, pdb]
   ```

```json
{"uses": "github://earthly/lunar-lib/policies/k8s@v1.0.0"}
```
"""

SELF_TEST_BAD = [
    ("no include", "  - uses: github://earthly/lunar-lib/collectors/k8s@v1.0.0\n    on: [k8s]\n",
     ["collectors/k8s", "has no `include:`", "t.md:5:"]),
    ("commented include", "  - uses: github://earthly/lunar-lib/policies/k8s@v1.0.0\n    # include: [pdb]\n",
     ["policies/k8s", "has no `include:`"]),
    ("exclude", "  - uses: github://earthly/lunar-lib/collectors/k8s@v1.0.0\n    exclude: [helm]\n",
     ["uses `exclude:`"]),
    ("empty include", "  - uses: github://earthly/lunar-lib/collectors/k8s@v1.0.0\n    include: []\n",
     ["non-empty list"]),
    ("unknown name", "  - uses: github://earthly/lunar-lib/policies/k8s@v1.0.0\n    include: [valid, pbd]\n",
     ["'pbd'", "aren't in its manifest"]),
    ("unknown plugin", "  - uses: github://earthly/lunar-lib/collectors/nope@v1.0.0\n    include: [x]\n",
     ["collectors/nope", "no such plugin"]),
    ("placeholder without include", "  - uses: github://earthly/lunar-lib/collectors/{path}@v1.0.0\n",
     ["has no `include:`"]),
    ("broken YAML", "  - uses: github://earthly/lunar-lib/collectors/k8s@v1.0.0\n   include: [k8s]\n",
     ["doesn't parse"]),
]


def self_test():
    items_for = lambda kind, name: SELF_TEST_ITEMS.get((kind, name))  # noqa: E731
    failures = []
    errors = check_markdown(SELF_TEST_GOOD, "good.md", items_for)
    if errors:
        failures.append("valid snippets were rejected:\n  " + "\n  ".join(errors))
    else:
        print("  OK  accepts: block and flow lists, name before uses, placeholders, other repos")
    for label, entry, expected in SELF_TEST_BAD:
        blob = "\n".join(check_markdown(f"# T\n\n```yaml\ncollectors:\n{entry}```\n", "t.md", items_for))
        missing = [token for token in expected if token not in blob]
        if missing:
            failures.append(f"{label}: expected {missing} in:\n  {blob or '(no errors)'}")
        else:
            print(f"  OK  rejects: {label}")
    if failures:
        print("\nSelf-test FAILED:\n" + "\n".join(failures))
        return 1
    print(f"Self-test passed (1 accepted, {len(SELF_TEST_BAD)} rejected).")
    return 0


def main():
    if "--self-test" in sys.argv[1:]:
        return self_test()

    # A glob that matches nothing means the +lint target didn't COPY that
    # directory, and the check would pass by reading nothing.
    files, empty = [], []
    for pattern in DOC_GLOBS:
        matched = sorted(glob.glob(pattern, recursive=True))
        files += matched
        if not matched:
            empty.append(pattern)
    if empty:
        print(f"No files matched {empty}: COPY the directory into +lint in the Earthfile.")
        return 1

    cache = {}

    def items_for(kind, name):
        if (kind, name) not in cache:
            cache[(kind, name)] = manifest_items(kind, name)
        return cache[(kind, name)]

    errors = []
    for path in files:
        errors += check_markdown(Path(path).read_text(), path, items_for)
    if errors:
        print("\n".join(errors))
        print(
            f"\n{len(errors)} lunar-lib import(s) in the docs need fixing. Every `uses:` "
            "entry lists what it runs with `include:`, so a reader who copies it doesn't "
            "pick up new sub-collectors or checks on a version bump."
        )
        return 1
    print(f"OK: every lunar-lib import in {len(files)} markdown files lists its `include:`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
