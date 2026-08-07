"""Typed value constraints for the required-annotations check.

Parses the ``required_annotations`` input and validates annotation values
against an optional constraint spec.

The input accepts two forms:

* a comma-separated string of keys (presence-only, the original behaviour), or
* a YAML list whose entries are either a bare key (presence-only) or a mapping
  with a ``key`` plus optional constraints (``type``, ``min``/``max``,
  ``min_length``/``max_length``, ``pattern``, ``enum``).

YAML parsing is delegated to ``yq`` (present in the policy base image), matching
how the backstage collector reads catalog-info.yaml — no extra Python
dependency is introduced.

Two failure modes, deliberately distinct:

* **Misconfiguration** — the constraint spec itself is broken (unknown type,
  ``min`` > ``max``, an invalid regex, a constraint applied to the wrong type,
  an enum value that is not of the declared type). This raises
  :class:`ConstraintConfigError` so the check surfaces as an *error*, and it is
  detected at parse time so it fires even when the annotation is absent.
* **Violation** — the annotation value is present but does not satisfy a valid
  constraint. :func:`validate_value` returns a human-readable message and the
  check *fails*.
"""

import json
import re
import subprocess

VALID_TYPES = ("string", "integer", "number", "boolean")

# Which constraint keys are meaningful for each declared type. A constraint
# outside its type's set is a misconfiguration rather than a silent no-op.
_COMMON = {"type", "enum"}
_ALLOWED_BY_TYPE = {
    "string": _COMMON | {"pattern", "min_length", "max_length"},
    "integer": _COMMON | {"min", "max"},
    "number": _COMMON | {"min", "max"},
    "boolean": _COMMON,
}


class ConstraintConfigError(ValueError):
    """Raised when the constraint spec itself is invalid (misconfiguration)."""


class _CoercionError(Exception):
    """Internal: a value/enum item cannot be read as the declared type."""


def parse_required_annotations(raw):
    """Parse the ``required_annotations`` input into a list of entries.

    Each entry is a dict ``{"key": str, "constraints": dict}``; ``constraints``
    is empty for presence-only entries. Raises :class:`ConstraintConfigError`
    on a malformed input or constraint spec.
    """
    raw = (raw or "").strip()
    if not raw:
        return []

    loaded = _load_input(raw)

    # A bare scalar is the legacy comma-separated, presence-only form.
    if loaded is None:
        return []
    if isinstance(loaded, str):
        return [
            {"key": k.strip(), "constraints": {}}
            for k in loaded.split(",")
            if k.strip()
        ]

    if not isinstance(loaded, list):
        raise ConstraintConfigError(
            "required_annotations must be a comma-separated string or a YAML "
            f"list, got {type(loaded).__name__}."
        )

    entries = []
    for item in loaded:
        if isinstance(item, str):
            key = item.strip()
            if key:
                entries.append({"key": key, "constraints": {}})
            continue
        if isinstance(item, dict):
            key = item.get("key")
            if not isinstance(key, str) or not key.strip():
                raise ConstraintConfigError(
                    "each required_annotations entry needs a non-empty string "
                    f"`key`, got: {item!r}."
                )
            constraints = {k: v for k, v in item.items() if k != "key"}
            _validate_constraint_spec(key.strip(), constraints)
            entries.append({"key": key.strip(), "constraints": constraints})
            continue
        raise ConstraintConfigError(
            "required_annotations entries must be a string or a mapping, got "
            f"{type(item).__name__}: {item!r}."
        )
    return entries


def validate_value(key, raw_value, constraints):
    """Validate a raw annotation value against a (pre-validated) constraint spec.

    Returns ``None`` if the value satisfies every constraint, or a
    human-readable failure message if it violates one.
    """
    declared_type = constraints.get("type", "string")

    try:
        value = _coerce(raw_value, declared_type)
    except _CoercionError:
        return (f'annotation "{key}": value "{raw_value}" is not a valid '
                f"{declared_type}")

    if "enum" in constraints and value not in constraints["enum"]:
        allowed = ", ".join(repr(v) for v in constraints["enum"])
        return (f'annotation "{key}": value "{raw_value}" is not one of the '
                f"allowed values ({allowed})")

    if "min" in constraints and value < constraints["min"]:
        return (f'annotation "{key}": value "{raw_value}" is below minimum '
                f'{constraints["min"]}')
    if "max" in constraints and value > constraints["max"]:
        return (f'annotation "{key}": value "{raw_value}" is above maximum '
                f'{constraints["max"]}')

    if "min_length" in constraints and len(value) < constraints["min_length"]:
        return (f'annotation "{key}": value "{raw_value}" is shorter than the '
                f'minimum length of {constraints["min_length"]}')
    if "max_length" in constraints and len(value) > constraints["max_length"]:
        return (f'annotation "{key}": value "{raw_value}" is longer than the '
                f'maximum length of {constraints["max_length"]}')

    if "pattern" in constraints and not re.fullmatch(constraints["pattern"], value):
        return (f'annotation "{key}": value "{raw_value}" does not match the '
                f'required pattern {constraints["pattern"]}')

    return None


def _load_input(raw):
    """Parse the raw input string as YAML (via yq), returning the JSON value."""
    try:
        proc = subprocess.run(
            ["yq", "-p=yaml", "-o=json", "."],
            input=raw,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        raise ConstraintConfigError(
            "required_annotations could not be parsed: `yq` is not available "
            "in the policy image."
        ) from e
    if proc.returncode != 0:
        raise ConstraintConfigError(
            f"required_annotations is not valid YAML: {proc.stderr.strip()}"
        )
    return json.loads(proc.stdout)


def _validate_constraint_spec(key, constraints):
    """Validate one constraint mapping. Raises ConstraintConfigError on misconfig.

    Enum items are coerced to the declared type in place, so downstream
    comparison happens in a single type domain (e.g. ``type: string`` with
    ``enum: [1, 2, 3]`` compares the strings ``"1"``, ``"2"``, ``"3"``).
    """
    declared_type = constraints.get("type", "string")
    if not isinstance(declared_type, str) or declared_type not in VALID_TYPES:
        raise ConstraintConfigError(
            f'annotation "{key}": unknown type {declared_type!r}. Valid types: '
            f"{', '.join(VALID_TYPES)}."
        )

    allowed = _ALLOWED_BY_TYPE[declared_type]
    unknown = sorted(k for k in constraints if k not in allowed)
    if unknown:
        raise ConstraintConfigError(
            f'annotation "{key}": constraint(s) {unknown} are not valid for '
            f'type "{declared_type}" (valid: {sorted(allowed)}).'
        )

    lo = _require_number(key, constraints, "min")
    hi = _require_number(key, constraints, "max")
    if lo is not None and hi is not None and lo > hi:
        raise ConstraintConfigError(
            f'annotation "{key}": min {lo} is greater than max {hi}.'
        )

    lo_len = _require_length(key, constraints, "min_length")
    hi_len = _require_length(key, constraints, "max_length")
    if lo_len is not None and hi_len is not None and lo_len > hi_len:
        raise ConstraintConfigError(
            f'annotation "{key}": min_length {lo_len} is greater than '
            f"max_length {hi_len}."
        )

    if "pattern" in constraints:
        pattern = constraints["pattern"]
        if not isinstance(pattern, str):
            raise ConstraintConfigError(
                f'annotation "{key}": pattern must be a string, got {pattern!r}.'
            )
        try:
            re.compile(pattern)
        except re.error as e:
            raise ConstraintConfigError(
                f'annotation "{key}": pattern is not a valid regex: {e}.'
            )

    if "enum" in constraints:
        enum = constraints["enum"]
        if not isinstance(enum, list) or not enum:
            raise ConstraintConfigError(
                f'annotation "{key}": enum must be a non-empty list, got {enum!r}.'
            )
        coerced = []
        for item in enum:
            try:
                coerced.append(_coerce(item, declared_type))
            except _CoercionError:
                raise ConstraintConfigError(
                    f'annotation "{key}": enum value {item!r} is not a valid '
                    f"{declared_type}."
                )
        constraints["enum"] = coerced


def _require_number(key, constraints, name):
    if name not in constraints:
        return None
    value = constraints[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConstraintConfigError(
            f'annotation "{key}": {name} must be a number, got {value!r}.'
        )
    return value


def _require_length(key, constraints, name):
    if name not in constraints:
        return None
    value = constraints[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConstraintConfigError(
            f'annotation "{key}": {name} must be a non-negative integer, got '
            f"{value!r}."
        )
    return value


def _coerce(raw, declared_type):
    """Coerce a value to the declared type, raising _CoercionError on failure.

    Annotation values arrive as strings, so coercion is defined in terms of the
    string form: ``"2"`` reads as the integer ``2`` but ``"2.5"`` does not.
    """
    if declared_type == "string":
        return str(raw)

    text = str(raw).strip()
    if declared_type == "integer":
        try:
            return int(text)
        except ValueError:
            raise _CoercionError()
    if declared_type == "number":
        try:
            return float(text)
        except ValueError:
            raise _CoercionError()
    if declared_type == "boolean":
        lowered = text.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        raise _CoercionError()

    raise _CoercionError()  # unreachable: type is validated before coercion
