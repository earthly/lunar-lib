#!/usr/bin/env python3
"""Validate that every earthly/lunar-lib image reference uses a canonical tag.

Plugin manifests pin their runtime image via `default_image` (and the related
`default_image_ci_collectors` / `default_image_non_ci_collectors` /
per-collector `image` fields). For the `earthly/lunar-lib` namespace, the only
tag form the release process knows how to rewrite is `<prefix>-main`:

    scripts/release.sh rewrites  earthly/lunar-lib:<prefix>-main
                              -> earthly/lunar-lib:<prefix>-vX.Y.Z  on release.

A dev/personal branch build (e.g. `trivy-brandon-trivy`, `grype-mybranch`,
`base-someexperiment`) does NOT match that `-main` rewrite, so it slips through
release.sh untouched and ships verbatim in the released manifest — pinning
customers to a throwaway image built from an older architecture. That is
exactly what happened in v1.5.0 with `earthly/lunar-lib:trivy-brandon-trivy`
(ENG-995): a real customer hit a bug because the released trivy collector
pointed at a personal dev image instead of `trivy-v1.5.0`.

This validator fails CI if any earthly/lunar-lib image reference uses a tag
that is neither:
  - the canonical `<prefix>-main` form (what lives on `main`), nor
  - a `<prefix>-vX.Y.Z` release tag (what release.sh produces on release
    branches, where `+lint` also runs — see .github/workflows/ci.yml).

Only the `earthly/lunar-lib:` namespace is checked. Third-party / vendor images
(public scanner images, `native`, etc.) are intentionally left alone.

Usage:
    python scripts/validate_image_tags.py
"""

import glob
import re
import sys

import yaml

MANIFEST_GLOBS = [
    "collectors/*/lunar-collector.yml",
    "policies/*/lunar-policy.yml",
    "catalogers/*/lunar-cataloger.yml",
]

# Finds an earthly/lunar-lib image reference inside a value and captures its tag
# (everything after the first ':'). The leading word boundary keeps a different
# org such as `notearthly/lunar-lib` from matching while still allowing a
# registry prefix like `docker.io/earthly/lunar-lib:...`.
LUNAR_LIB_REF = re.compile(r"\bearthly/lunar-lib:(\S+)")

# Accepted tag forms: `<prefix>-main` or a `<prefix>-vX.Y.Z` release tag.
ALLOWED_TAG = re.compile(r"(?:-main|-v[0-9]+\.[0-9]+\.[0-9]+)$")


def iter_image_values(node):
    """Yield (key, value) for every string value under a key containing 'image'.

    Walks the parsed YAML recursively so `default_image*` fields and any
    per-collector `image:` overrides are all covered regardless of nesting.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and "image" in key.lower() and isinstance(value, str):
                yield key, value
            yield from iter_image_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_image_values(item)


def validate_manifest(path):
    """Return a list of error strings for one manifest file (empty == OK)."""
    with open(path) as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [f"  Invalid YAML: {e}"]

    # Best-effort hint: the conventional prefix is the plugin's own directory
    # name (e.g. collectors/trivy -> `trivy-main`), or `base-main` for plugins
    # without a custom image.
    plugin_dir = path.split("/")[1] if "/" in path else path

    errors = []
    for key, value in iter_image_values(data):
        match = LUNAR_LIB_REF.search(value)
        if not match:
            continue  # not an earthly/lunar-lib image — leave third-party refs alone
        tag = match.group(1)
        if ALLOWED_TAG.search(tag):
            continue
        errors.append(
            f"  {key}: earthly/lunar-lib:{tag}\n"
            f"      Tag '{tag}' is not the canonical '<prefix>-main' form.\n"
            f"      Use 'earthly/lunar-lib:{plugin_dir}-main' (custom image) or "
            f"'earthly/lunar-lib:base-main' (shared base image).\n"
            f"      Dev/personal branch tags are not rewritten by scripts/release.sh "
            f"and must not be committed."
        )
    return errors


def main():
    manifests = sorted(
        path for pattern in MANIFEST_GLOBS for path in glob.glob(pattern)
    )

    if not manifests:
        print("No plugin manifests found.")
        return 0

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
        print("Image tag validation failed.")
        print(
            "Every earthly/lunar-lib image must use the canonical '<prefix>-main' tag "
            "so scripts/release.sh can rewrite it to '<prefix>-vX.Y.Z' on release."
        )
        return 1

    print(f"OK: {len(manifests)} manifest(s) validated — all earthly/lunar-lib images use canonical tags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
