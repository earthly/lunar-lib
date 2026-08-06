#!/usr/bin/env python3
"""Lint a parsed Backstage catalog-info descriptor and output structured JSON.

Reads parsed YAML-as-JSON from stdin, runs schema checks, and prints a JSON
object matching the `.catalog.native.backstage` schema to stdout.

Schema checks (Backstage descriptor format — https://backstage.io/docs/features/software-catalog/descriptor-format):
- Top-level must be a mapping
- apiVersion: required, string, should start with `backstage.io/`
- kind: required, string, should be one of the known kinds
- metadata.name: required, string, DNS-compatible
- metadata.tags: each tag must be a valid Backstage tag (lowercase [a-z0-9+#]
  segments, dash-separated, at most 63 chars) — the server rejects otherwise
- spec: required mapping for non-Location kinds
"""

import argparse
import json
import re
import sys

NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9\-_.]*[a-z0-9])?$")

# Backstage validates every metadata.tags entry with this exact rule
# (@backstage/catalog-model Validators.isValidTag): lowercase [a-z0-9+#] segments
# joined by single dashes, 1-63 chars. The catalog-info.yaml *schema* only
# requires a non-empty string (no pattern), so a tag like "hosting/internal"
# passes YAML/schema validation but the Backstage *server* rejects the whole
# entity at ingest ("Policy check failed ... 'tags.0' is not valid; expected a
# string that is sequences of [a-z0-9+#] separated by [-], at most 63
# characters"). We replicate the server-side rule here so the problem surfaces
# in CI (via the catalog-info-valid check) instead of at Backstage registration.
TAG_RE = re.compile(r"^[a-z0-9+#]+(-[a-z0-9+#]+)*$")
TAG_MAX_LEN = 63

KNOWN_KINDS = {
    "Component",
    "API",
    "Resource",
    "System",
    "Domain",
    "Group",
    "User",
    "Location",
    "Template",
}


def _err(errors, message, severity="error"):
    errors.append({"line": 0, "message": message, "severity": severity})


def _lint_tags(errors, tags):
    """Validate metadata.tags against Backstage's isValidTag rule.

    Backstage hard-rejects an entity whose tags don't conform (the whole
    component fails to register), so these are errors, not warnings — a bad tag
    means the catalog-info.yaml never lands in Backstage at all.
    """
    if tags is None:
        return
    if not isinstance(tags, list):
        _err(errors, "metadata.tags must be a list of strings")
        return
    for i, tag in enumerate(tags):
        if not isinstance(tag, str) or not tag:
            _err(errors, f"metadata.tags[{i}] must be a non-empty string")
            continue
        if not TAG_RE.match(tag):
            _err(
                errors,
                f"metadata.tags[{i}] '{tag}' is not a valid Backstage tag: use "
                "lowercase letters, digits, '+' or '#' in dash-separated segments "
                "(e.g. 'hosting-internal') — no slashes, spaces, dots, or "
                "uppercase. Backstage will reject the entity at registration.",
            )
        elif len(tag) > TAG_MAX_LEN:
            _err(
                errors,
                f"metadata.tags[{i}] '{tag}' exceeds {TAG_MAX_LEN} characters. "
                "Backstage will reject the entity at registration.",
            )


def lint(parsed, path):
    errors = []

    if not isinstance(parsed, dict):
        _err(errors, "Top-level must be a YAML mapping")
        return {
            "valid": False,
            "errors": errors,
            "path": path,
        }

    api_version = parsed.get("apiVersion")
    if api_version in (None, ""):
        _err(errors, "Missing required field: apiVersion")
    elif not isinstance(api_version, str):
        _err(errors, "apiVersion must be a string")
    elif not api_version.startswith("backstage.io/"):
        _err(
            errors,
            f"apiVersion should start with 'backstage.io/' (got '{api_version}')",
            severity="warning",
        )

    kind = parsed.get("kind")
    if kind in (None, ""):
        _err(errors, "Missing required field: kind")
    elif not isinstance(kind, str):
        _err(errors, "kind must be a string")
    elif kind not in KNOWN_KINDS:
        _err(
            errors,
            f"Unknown kind '{kind}' (expected one of: {', '.join(sorted(KNOWN_KINDS))})",
            severity="warning",
        )

    metadata = parsed.get("metadata")
    if metadata is None:
        _err(errors, "Missing required field: metadata")
        metadata = {}
    elif not isinstance(metadata, dict):
        _err(errors, "metadata must be a mapping")
        metadata = {}
    else:
        meta_name = metadata.get("name")
        if meta_name in (None, ""):
            _err(errors, "Missing required field: metadata.name")
        elif not isinstance(meta_name, str):
            _err(errors, "metadata.name must be a string")
        elif not NAME_RE.match(meta_name):
            _err(
                errors,
                f"metadata.name '{meta_name}' is not DNS-compatible "
                "(lowercase alphanumeric, dash, dot, underscore; must start and end with alphanumeric)",
                severity="warning",
            )

        _lint_tags(errors, metadata.get("tags"))

    spec = parsed.get("spec")
    if spec is None:
        if kind and kind != "Location":
            _err(errors, f"{kind} should have a 'spec' section", severity="warning")
    elif not isinstance(spec, dict):
        _err(errors, "spec must be a mapping")

    valid = not any(e["severity"] == "error" for e in errors)

    output = {
        "valid": valid,
        "errors": errors,
        "path": path,
    }
    if isinstance(api_version, str) and api_version:
        output["apiVersion"] = api_version
    if isinstance(kind, str) and kind:
        output["kind"] = kind
    if isinstance(metadata, dict) and metadata:
        output["metadata"] = metadata
    if isinstance(spec, dict):
        output["spec"] = spec

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    args = parser.parse_args()

    try:
        parsed = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        result = {
            "valid": False,
            "errors": [
                {"line": 0, "message": f"Invalid parser output: {e}", "severity": "error"}
            ],
            "path": args.path,
        }
    else:
        result = lint(parsed, args.path)

    json.dump(result, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
