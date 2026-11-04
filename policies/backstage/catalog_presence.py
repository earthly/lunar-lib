"""Opt-in skip for components that have no catalog-info.yaml.

The `backstage` collector writes nothing when it finds no catalog file, so the
absence of `.catalog.native.backstage` is the "not Backstage-managed" signal.
Failing on it is the right default — the user opted into Backstage enforcement
— but it is the wrong answer for a fleet where only some repos are catalogued.
`skip_when_no_catalog_info` flips that absence to a skip.

With the collector's `catalog_api_fallback`, the namespace can instead hold an
entity fetched from the Backstage catalog API, recognizable by having no
`path`. The file checks treat it as no file; every other check evaluates it,
pointing its failure text at the file Backstage loaded the entity from.
"""

from lunar_policy import variable_or_default

SKIP_REASON = (
    "No catalog-info.yaml found and skip_when_no_catalog_info is set, so this "
    "component is treated as not Backstage-managed."
)


def skip_when_no_catalog_info():
    """Whether the operator opted into skipping instead of enforcing."""
    return (
        variable_or_default("skip_when_no_catalog_info", "false").strip().lower()
        == "true"
    )


def skip_if_no_catalog(c):
    """Skip `c` when the component has no catalog-info.yaml and the mode is on.

    Raises `SkippedError` (via `Check.skip`) when it applies, so callers below
    this line only handle the enforce path. The short-circuit on the input is
    deliberate: with the default off, `exists()` is never called and every
    check keeps its current pending/fail semantics exactly.
    """
    if skip_when_no_catalog_info() and not c.exists(".catalog.native.backstage"):
        c.skip(SKIP_REASON)


def fetched_from_catalog(c):
    """Whether `.catalog.native.backstage` holds an entity fetched from the
    catalog API rather than a parsed file. The collector writes the namespace in
    one go, so once it exists, a missing `path` is final, not pending."""
    data = c.get_value_or_default(".catalog.native.backstage", None)
    return isinstance(data, dict) and data.get("path") is None


def require_catalog_file():
    """Whether the file checks need a literal catalog-info.yaml (the default),
    or also accept an entity fetched from the catalog API."""
    return variable_or_default("require_catalog_file", "true").strip().lower() != "false"


def fetched_counts_as_no_file(c):
    """A fetched entity that the file checks must treat as a missing file."""
    return fetched_from_catalog(c) and require_catalog_file()


def skip_if_no_catalog_file(c):
    """`skip_if_no_catalog` for the checks about the file itself, where an
    entity fetched from the catalog API counts as no file unless
    `require_catalog_file` is off."""
    if skip_when_no_catalog_info() and (
        not c.exists(".catalog.native.backstage") or fetched_counts_as_no_file(c)
    ):
        c.skip(SKIP_REASON)


FETCHED_NO_FILE = (
    "No catalog-info.yaml found in the repository; this component's entity was "
    "fetched from the Backstage catalog instead. Add a catalog-info.yaml, or set "
    'the policy\'s `require_catalog_file` input to "false" to accept an entity '
    "that is in Backstage."
)


def _entity_location(c):
    annotations = c.get_value_or_default(".catalog.native.backstage.metadata.annotations", {})
    if not isinstance(annotations, dict):
        return None
    for key in ("backstage.io/view-url", "backstage.io/managed-by-location"):
        value = annotations.get(key)
        if isinstance(value, str) and value.strip():
            value = value.strip()
            for prefix in ("url:", "file:"):
                if value.startswith(prefix):
                    value = value[len(prefix):]
            return value
    return None


def in_source(c, text):
    """`text` with "catalog-info.yaml" pointing at where a fetched entity is
    defined; unchanged for an entity read from a file."""
    if "catalog-info.yaml" not in text or not fetched_from_catalog(c):
        return text
    location = _entity_location(c)
    entity = f"Backstage entity (defined in {location})" if location else "Backstage entity"
    text = text.replace("This component's catalog-info.yaml", f"This component's {entity}")
    if text.startswith("catalog-info.yaml"):
        text = f"The {entity}" + text[len("catalog-info.yaml"):]
    return text.replace("catalog-info.yaml", f"the {entity}")


def fail(c, message):
    c.fail(in_source(c, message))


def skip(c, reason):
    c.skip(in_source(c, reason))
