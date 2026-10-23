"""Opt-in skip for components that have no catalog-info.yaml.

The `backstage` collector writes nothing when it finds no catalog file, so the
absence of `.catalog.native.backstage` is the "not Backstage-managed" signal.
Failing on it is the right default — the user opted into Backstage enforcement
— but it is the wrong answer for a fleet where only some repos are catalogued.
`skip_when_no_catalog_info` flips that absence to a skip.
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
