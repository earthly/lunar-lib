"""Shared helpers for the registry-provenance policies."""


def describe_registry(entry):
    """Human-readable description of where a registry declaration came from."""
    ecosystem = entry.get_value(".ecosystem")
    host = entry.get_value(".host")
    path = entry.get_value_or_default(".path", "")
    name = entry.get_value_or_default(".name", None)

    if entry.get_value_or_default(".is_default", False):
        where = f"no registry configured in {path}" if path else "no registry configured"
        return f"{ecosystem} resolves from '{host}' (ecosystem default, {where})"

    scope = f" for '{name}'" if name else ""
    where = f" configured in {path}" if path else ""
    return f"{ecosystem} registry '{host}'{scope}{where}"


def is_dependency_source(entry):
    """Whether this declaration is somewhere dependencies are pulled *from*.

    Publishing targets are excluded: a project that consumes from an internal
    registry may still legitimately publish to a public one.
    """
    return entry.get_value_or_default(".kind", "primary") != "publish"
