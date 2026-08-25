#!/usr/bin/env python3
"""Validate that plugin manifests only use keys the hub actually decodes.

Nothing in the hub decodes a plugin manifest with `KnownFields(true)`, so an
unknown key is *silently dropped* — no error, no warning, and `ValidateCollector`
still passes. A key written at the wrong nesting level therefore looks correct
in review and does nothing at runtime.

The motivating case (ENG-1601, surfaced during a customer investigation):

    collectors:
      - name: github-app
        hook:
          type: code
          runs_on: [prs]      # <- silently ignored

`runs_on` is a field of `manifest.Snippet`, not of `manifest.Hook`. Nested under
`hook:` it is dropped at decode time, `defaultsSnippets` then fills the empty
snippet-level value with the `[prs, default-branch]` default, and the
sub-collector runs in *both* contexts while the manifest claims otherwise. Five
sub-collectors across three plugins were wrong this way before anyone noticed.

This validator closes that gap. Across every file the hub decodes into
`manifest.Snippet` — the plugin manifests and the starter-pack consumer configs
— it fails on any snippet key outside the snippet allow-list, and on any key of
a `hook:` / `hooks[]` mapping outside the hook allow-list.

Scope is deliberately narrow — unknown keys only. Required-key and value-shape
validation is ENG-757, which will extend this same script rather than add a
second one.

Probe manifests (`probes/*/lunar-probe.yml`) are intentionally excluded: they
are consumed by lunar-probe, not by the hub's `manifest` package, and have a
different schema (`check`, `message`, `requires`, snippet-level `inputs`, and
`paths` under `hook:`).

Usage:
    python scripts/validate_manifest_schema.py
    python scripts/validate_manifest_schema.py --self-test
"""

import glob
import sys

import yaml

MANIFEST_GLOBS = [
    "collectors/*/lunar-collector.yml",
    "policies/*/lunar-policy.yml",
    "catalogers/*/lunar-cataloger.yml",
    # Starter-pack consumer configs. Their `collectors:` / `policies:` entries are
    # import sites rather than definitions, but the hub decodes them into the same
    # manifest.Snippet, so the same keys are legal and the same typo is possible —
    # and these are the files users copy.
    "starter-packs/*/*/lunar-config.yml",
]

# Top-level keys holding a list of snippets, per manifest.{Collector,Policy,
# Cataloger}Plugin in earthly/lunar.
SNIPPET_LIST_KEYS = ("collectors", "policies", "catalogers")

# Every yaml tag on manifest.Snippet (hub/manifest/manifest.go). Fields tagged
# `yaml:"-"` (SourceFile, Line) are provenance stamped by the loader, not
# decoded, so they are not accepted here.
SNIPPET_KEYS = {
    "name",
    "description",
    "enforcement",
    "uses",
    "on",
    "runPython",
    "mainPython",
    "runBash",
    "mainBash",
    "with",
    "hook",
    "hooks",
    "initiative",
    "image",
    "runs_on",
    "size",
    "include",
    "exclude",
}

# Presentation-only keys that the hub ignores by design. `keywords` powers the
# plugin landing pages on the website and is *required* by
# validate_landing_page_metadata.py, so it must not be flagged here.
LUNAR_LIB_ONLY_SNIPPET_KEYS = {"keywords"}

ALLOWED_SNIPPET_KEYS = SNIPPET_KEYS | LUNAR_LIB_ONLY_SNIPPET_KEYS

# Every yaml tag on manifest.Hook (hub/manifest/manifest.go).
ALLOWED_HOOK_KEYS = {
    "type",
    "pattern",
    "schedule",
    "repo",
    "clone-code",
    "binary",
    "args",
    "args_pattern",
    "envs",
    "path",
}

# Keys that are valid *somewhere*, just not where they were written. Naming the
# right home turns "unknown key" into an actionable fix.
MISPLACED_HINTS = {
    "runs_on": (
        "`runs_on` is a snippet-level field (manifest.Snippet.RunsOn); "
        "manifest.Hook has no `runs_on`.\n"
        "      Move it up one level, to the same indent as `name:` — or delete it "
        "if the snippet\n"
        "      should run in both contexts (the default is [prs, default-branch])."
    ),
}


def mapping_items(node):
    """Yield (key, value_node, line) for a YAML MappingNode. Non-mappings yield nothing."""
    if not isinstance(node, yaml.MappingNode):
        return
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode):
            yield key_node.value, value_node, key_node.start_mark.line + 1


def sequence_items(node):
    """Yield each element node of a YAML SequenceNode. Non-sequences yield nothing."""
    if isinstance(node, yaml.SequenceNode):
        yield from node.value


def snippet_name(snippet_node):
    """Best identifier for a snippet: its `name`, or the `uses` it imports."""
    found = {}
    for key, value_node, _ in mapping_items(snippet_node):
        if key in ("name", "uses") and isinstance(value_node, yaml.ScalarNode):
            found[key] = value_node.value
    # Plugin manifests define snippets and always carry `name`; consumer configs
    # import them and carry only `uses`.
    return found.get("name") or found.get("uses") or "<unnamed>"


def check_keys(node, allowed, where, errors):
    """Append an error for every key of `node` that is not in `allowed`."""
    for key, _, line in mapping_items(node):
        if key in allowed:
            continue
        error = f"  {where}.{key} (line {line}): unknown key — the hub silently ignores it"
        hint = MISPLACED_HINTS.get(key)
        if hint:
            error += f"\n      {hint}"
        errors.append(error)


def validate_source(text):
    """Return a list of error strings for one manifest's YAML text (empty == OK)."""
    try:
        root = yaml.compose(text)
    except yaml.YAMLError as e:
        return [f"  Invalid YAML: {e}"]

    errors = []
    for list_key, list_node, _ in mapping_items(root):
        if list_key not in SNIPPET_LIST_KEYS:
            continue
        for snippet_node in sequence_items(list_node):
            where = f"{list_key}[{snippet_name(snippet_node)}]"
            check_keys(snippet_node, ALLOWED_SNIPPET_KEYS, where, errors)

            for key, value_node, _ in mapping_items(snippet_node):
                if key == "hook":
                    check_keys(value_node, ALLOWED_HOOK_KEYS, f"{where}.hook", errors)
                elif key == "hooks":
                    for i, hook_node in enumerate(sequence_items(value_node)):
                        check_keys(
                            hook_node, ALLOWED_HOOK_KEYS, f"{where}.hooks[{i}]", errors
                        )
    return errors


def validate_manifest(path):
    with open(path) as f:
        return validate_source(f.read())


# --- self-test -------------------------------------------------------------
#
# The bug this script exists to catch is invisible to the naked eye, so assert
# it mechanically instead of eyeballing the tree. Run via `--self-test`; +lint
# runs it before the real scan so a regression in the checker itself fails CI
# even when every committed manifest happens to be clean.

BAD_MANIFEST = """
name: example
collectors:
  - name: github-app
    mainBash: github-app.sh
    hook:
      type: code
      runs_on: [prs]
    keywords: ["example"]
"""

BAD_HOOKS_LIST = """
name: example
policies:
  - name: check-it
    mainPython: check.py
    hooks:
      - type: code
        bogus_key: true
    keywords: ["example"]
"""

BAD_SNIPPET_KEY = """
name: example
catalogers:
  - name: discover
    mainBash: discover.sh
    run_on: [prs]
    keywords: ["example"]
"""

# A consumer-config import site: no `name:`, so the error has to identify the
# snippet by `uses:` instead.
BAD_IMPORT_SITE = """
version: 1
policies:
  - uses: github://earthly/lunar-lib/policies/sast
    enforcement: block-pr
    hook:
      type: code
      runs_on: [prs]
"""

GOOD_MANIFEST = """
name: example
collectors:
  - name: github-app
    mainBash: github-app.sh
    runs_on: [prs]
    hook:
      type: code
    keywords: ["example"]
  - name: cicd
    mainBash: cicd.sh
    size: large
    hooks:
      - type: ci-after-command
        binary:
          name: example
      - type: after-json
        path: .sca
    keywords: ["example"]
"""


def self_test():
    cases = [
        # The `snippet-level` token pins the MISPLACED_HINTS text specifically:
        # without it the assertion passes on the generic "unknown key" line
        # alone, which already contains the word `runs_on`.
        (
            "runs_on under hook:",
            BAD_MANIFEST,
            ["runs_on", "github-app", "line 8", "snippet-level"],
        ),
        ("unknown key in hooks[]", BAD_HOOKS_LIST, ["bogus_key", "check-it", "hooks[0]"]),
        ("typo'd snippet key", BAD_SNIPPET_KEY, ["run_on", "discover"]),
        (
            "import site with no name:",
            BAD_IMPORT_SITE,
            ["runs_on", "policies/sast", "snippet-level"],
        ),
    ]

    failures = []
    for label, source, expected in cases:
        errors = validate_source(source)
        blob = "\n".join(errors)
        if not errors:
            failures.append(f"  {label}: expected a failure, got none")
            continue
        missing = [token for token in expected if token not in blob]
        if missing:
            failures.append(f"  {label}: error text is missing {missing}\n{blob}")
        else:
            print(f"  OK  rejects: {label}")

    good_errors = validate_source(GOOD_MANIFEST)
    if good_errors:
        failures.append("  valid manifest: expected no errors, got:\n" + "\n".join(good_errors))
    else:
        print("  OK  accepts: valid snippet-level runs_on, hook, hooks[], size")

    # `keywords` is hub-ignored but required by the landing-page validator — a
    # future tightening of the allow-list must not start rejecting it.
    if validate_source(GOOD_MANIFEST.replace('    keywords: ["example"]\n', "")):
        failures.append("  keywords: removing it changed the verdict — allow-list is coupled to it")

    if failures:
        print("\nSelf-test FAILED:")
        for f in failures:
            print(f)
        return 1

    print(f"Self-test passed ({len(cases)} rejected, 1 accepted).")
    return 0


def main():
    if "--self-test" in sys.argv[1:]:
        return self_test()

    # A glob that matches nothing means this validator is silently checking less
    # than it claims — the exact failure mode it exists to catch. The `+lint`
    # target only COPYs the directories it knows about, so a new glob without a
    # matching COPY would otherwise pass by scanning zero files.
    empty = [pattern for pattern in MANIFEST_GLOBS if not glob.glob(pattern)]
    if empty:
        print("Manifest schema validation failed.")
        for pattern in empty:
            print(f"  No files matched '{pattern}' — nothing was checked.")
        print(
            "Either the glob is stale, or the directory was not COPYed into the "
            "+lint target in the Earthfile."
        )
        return 1

    manifests = sorted(path for pattern in MANIFEST_GLOBS for path in glob.glob(pattern))

    failed = False
    for path in manifests:
        errors = validate_manifest(path)
        if errors:
            failed = True
            print(f"FAIL: {path}")
            for e in errors:
                print(e)
            print()

    if failed:
        print("Manifest schema validation failed.")
        print(
            "The hub does not decode plugin manifests with KnownFields(true), so an "
            "unknown key is dropped silently rather than rejected. Remove it, or move "
            "it to the level the hub reads it from."
        )
        return 1

    print(f"OK: {len(manifests)} manifest(s) validated — no unknown snippet or hook keys.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
