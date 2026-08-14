#!/usr/bin/env python3
"""Lint a parsed Backstage catalog-info descriptor and output structured JSON.

Reads parsed YAML-as-JSON from stdin — either a single entity object or a JSON
array of entities (a `catalog-info.yaml` may declare several entities separated
by `---`) — runs schema checks on each, and prints one JSON object matching the
`.catalog.native.backstage` schema to stdout. When multiple entities are
present, `valid`/`errors` aggregate across all of them, the first Component (or
first entity) is hoisted to the top level, and every entity is listed under
`entities[]`. See `lint_documents` for the aggregate shape.

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
# (@backstage/catalog-model CommonValidatorFunctions.isValidTag): lowercase
# [a-z0-9+#] segments joined by single dashes, 1-63 chars. The catalog-info.yaml
# *schema* only requires a non-empty string (no pattern), so a tag like
# "hosting/internal" passes YAML/schema validation but the Backstage *server*
# rejects the whole entity at ingest ("Policy check failed ... 'tags.0' is not
# valid; expected a string that is sequences of [a-z0-9+#] separated by [-], at
# most 63 characters"). We replicate the server-side rule here so the problem
# surfaces in CI (via the catalog-info-valid check) instead of at Backstage
# registration.
#
# Match the CODE, not the descriptor-format docs: the docs prose lists
# "[a-z0-9:+#]" (with a colon), but isValidTag does NOT allow a colon. Following
# the docs would let e.g. "type:service" pass this lint and still be rejected by
# Backstage — the exact failure we're preventing. Widen only if isValidTag does.
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


def _entity_label(entity, index):
    """Human locator for one entity within a multi-document file.

    Used to prefix aggregated error messages so a reader can tell which `---`
    document is at fault (e.g. ``document 2 (API 'payment-api-grpc')``).
    """
    kind = entity.get("kind")
    metadata = entity.get("metadata")
    name = metadata.get("name") if isinstance(metadata, dict) else None
    if kind and name:
        detail = f"{kind} '{name}'"
    elif kind:
        detail = str(kind)
    elif name:
        detail = f"'{name}'"
    else:
        detail = "unnamed"
    return f"document {index + 1} ({detail})"


def lint_documents(docs, path):
    """Lint every entity in a (possibly multi-document) catalog-info file.

    A single ``catalog-info.yaml`` may declare multiple Backstage entities
    separated by ``---`` (e.g. a Component plus the APIs it provides). ``docs``
    is the list of parsed YAML documents. Returns the aggregate
    ``.catalog.native.backstage`` object:

    - ``valid`` is true only when *every* entity is valid.
    - ``errors`` concatenates every entity's findings. In a multi-entity file
      each message is prefixed with a ``document N (Kind 'name')`` locator and
      carries an ``entity`` index into ``entities[]``; a single-entity file
      keeps messages byte-identical to the pre-multi-doc output.
    - the first ``Component`` (else the first entity) is hoisted to the top
      level (``apiVersion``/``kind``/``metadata``/``spec``) for backward
      compatibility — the owner/lifecycle/system/annotation/tag policies read
      those paths and pre-date multi-doc support.
    - ``entities[]`` lists every parsed entity (its own ``valid``/``errors`` plus
      raw fields) so a policy can inspect all of them, not just the primary.
    """
    # A bare `---`, a trailing separator, or a blank file yields null documents;
    # Backstage's loader ignores them, so they are not entities.
    entities_in = [doc for doc in docs if doc is not None]

    if not entities_in:
        return {
            "valid": False,
            "errors": [
                {
                    "line": 0,
                    "message": "catalog-info.yaml declares no entities",
                    "severity": "error",
                }
            ],
            "path": path,
        }

    linted = [lint(doc, path) for doc in entities_in]
    multi = len(linted) > 1

    errors = []
    for index, entity in enumerate(linted):
        for err in entity["errors"]:
            if multi:
                err = {
                    **err,
                    "message": f"{_entity_label(entity, index)}: {err['message']}",
                    "entity": index,
                }
            errors.append(err)

    # First Component wins as the "primary" entity hoisted to the top level:
    # owner/lifecycle/system live on Component in the Backstage model, and
    # one-Component-plus-its-APIs is the common multi-doc shape. Fall back to the
    # first entity when there is no Component (e.g. a System+Domain file).
    primary = next((e for e in linted if e.get("kind") == "Component"), linted[0])

    output = {
        "valid": all(e["valid"] for e in linted),
        "errors": errors,
        "path": path,
    }
    for field in ("apiVersion", "kind", "metadata", "spec"):
        if field in primary:
            output[field] = primary[field]

    # Per-entity view (path is redundant with the top-level one, so drop it).
    output["entities"] = [
        {k: v for k, v in e.items() if k != "path"} for e in linted
    ]
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
        # main.sh pipes a JSON array of documents (`yq ea -o=json '[.]'`); accept
        # a bare object too so a single parsed entity still lints correctly.
        docs = parsed if isinstance(parsed, list) else [parsed]
        result = lint_documents(docs, args.path)

    json.dump(result, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
