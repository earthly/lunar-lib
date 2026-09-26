"""Shared helpers for the ticket checks."""

import json

from lunar_policy import variable_or_default
from lunar_policy.nodepath import NodePath

DEFAULT_TICKET_PATH = ".vcs.pr.ticket"

# Jira returns a select-list option as {"value": ...}, a status, priority or
# component as {"name": ...} and a user as {"displayName": ...}. A user can
# also carry the deprecated `name` as "", so the first non-empty key wins.
DISPLAY_KEYS = ("value", "name", "displayName")


def ticket_path():
    """Where the checks read the ticket from: `.vcs.pr.ticket` unless the
    `ticket_path` input points them at another reference, such as the one a
    second jira collector import records."""
    path = variable_or_default("ticket_path", "").strip() or DEFAULT_TICKET_PATH
    if not path.startswith("."):
        path = "." + path
    return checked(path)


def checked(path):
    """Raises ValueError on a malformed path. exists() and
    get_value_or_default() swallow the SDK's parse error, which would turn a
    typo into "no ticket" or "no value" instead of an error."""
    NodePath.parse(path)
    return path


def missing_ticket_message(path):
    if path == DEFAULT_TICKET_PATH:
        return ("PR does not reference a ticket. "
                "Include a ticket ID in the PR title (e.g. [ABC-123]).")
    return (f"PR does not reference a ticket for {path}. "
            "Include its key in the PR title or description.")


def parse_list(name, raw):
    """A list input given comma-separated, one entry per line, or as a JSON
    array (the form for entries that contain a comma)."""
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"{name}: invalid JSON array: {e}")
        if not isinstance(items, list):
            raise ValueError(f"{name}: expected a JSON array")
        entries = [_scalar(i) for i in items]
    else:
        entries = [e for line in raw.splitlines() for e in line.split(",")]
    return [e.strip() for e in entries if e.strip()]


def is_empty(value):
    """True for a field Jira reports as unset: null, "", [] or {}."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return all(is_empty(v) for v in value)
    if isinstance(value, dict):
        return not value
    return False


def field_values(field, value):
    """The values of a ticket field to compare against an allowed list: one per
    item for a list (labels, multi-select), the display key of an object, or
    the scalar itself.

    Raises ValueError for an object with no display key, such as a rich-text
    document, since nothing in it can be compared.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [v for item in value for v in field_values(field, item)]
    if isinstance(value, dict):
        for key in DISPLAY_KEYS:
            display = value.get(key)
            if display not in (None, "") and not isinstance(display, (dict, list)):
                return [_scalar(display)]
        raise ValueError(
            f"ticket_field {field} is an object without a value, name or "
            f"displayName to compare. Point ticket_field at one of its keys "
            f"instead (e.g. {field}.id).")
    text = _scalar(value).strip()
    return [text] if text else []


def _scalar(value):
    # JSON spelling, so a Jira number field returned as 5.0 matches "5" and a
    # boolean matches "true".
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
