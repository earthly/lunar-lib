import json
import re
from typing import NamedTuple, Optional

from lunar_policy import Check, variable_or_default

# JEP 322 version strings, as java.lang.Runtime.Version parses them:
# 21, 21.0.5, 21.0.13.1, 21.0.5+11, 21.0.5+11-LTS, 27-ea, 27-ea+12.
_MODERN = re.compile(
    r"(?P<num>\d+(?:\.\d+)*)"
    r"(?:-(?P<pre>[A-Za-z0-9]+))?"
    r"(?P<plus>\+(?P<build>\d+)?)?"
    r"(?:-(?P<opt>[-A-Za-z0-9.]+))?"
)
# Java 8 and earlier: 1.8, 1.8.0, 1.8.0_202, 1.8.0_202-b08, 1.8.0_202-ea-b03.
_LEGACY = re.compile(
    r"1\.(?P<feature>\d+)(?:\.(?P<minor>\d+)(?:_(?P<update>\d+))?)?"
    r"(?:-(?!b\d+$)(?P<pre>[A-Za-z0-9]+))?"
    r"(?:-b\d+)?"
)
# Update release names: 8u202, 8u202-b08, 8u202b08.
_UPDATE_NAME = re.compile(r"(?P<feature>\d+)u(?P<update>\d+)(?:-?b\d+)?")

_FORMS = "21, 21.0.13.1, 21.0.5+11-LTS, 27-ea, 1.8.0_202 or 8u202"
_JSON_TYPES = {bool: "boolean", type(None): "null", dict: "object", list: "array"}


class JavaVersion(NamedTuple):
    text: str
    numbers: tuple  # feature, interim, update, patch, ...
    pre: Optional[str]  # pre-release identifier, e.g. "ea"


def parse_java_version(value):
    """Parse a Java version into a JavaVersion; raise ValueError if unsupported.

    Legacy versions map onto modern numbering: 1.8.0_202 and 8u202 are both
    (8, 0, 202). Build numbers and optional info (+11, -LTS, -b08) are dropped.
    """
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        kind = _JSON_TYPES.get(type(value), type(value).__name__)
        raise ValueError(f"must be a string such as \"21.0.5\", got {kind}")
    text = str(value).strip()

    m = _LEGACY.fullmatch(text)
    if m:
        numbers = [m["feature"], m["minor"], m["update"]]
        return JavaVersion(text, tuple(int(n) for n in numbers if n is not None), m["pre"])
    m = _UPDATE_NAME.fullmatch(text)
    if m:
        return JavaVersion(text, (int(m["feature"]), 0, int(m["update"])), None)
    m = _MODERN.fullmatch(text)
    # A bare "+" needs a build number or optional info after it ("21+" is invalid).
    if m and not (m["plus"] and m["build"] is None and m["opt"] is None):
        return JavaVersion(text, tuple(int(n) for n in m["num"].split(".")), m["pre"])
    raise ValueError(f"is not a recognized version format; expected a form like {_FORMS}")


def _compare_pre(a, b):
    # java.lang.Runtime.Version order: a release sorts after any pre-release of
    # it, and numeric identifiers sort numerically, before alphanumeric ones.
    if a == b:
        return 0
    if a is None:
        return 1
    if b is None:
        return -1
    if a.isdigit() and b.isdigit():
        return (int(a) > int(b)) - (int(a) < int(b))
    if a.isdigit() or b.isdigit():
        return -1 if a.isdigit() else 1
    return (a > b) - (a < b)


def compare_java_versions(a, b):
    """Return a negative number, zero or a positive number as a <, ==, > b.

    Numbers compare element by element and missing trailing elements count as
    zero, so 21 == 21.0.0 and 21.0.5 < 21.0.13.1. On equal numbers a
    pre-release sorts before the release: 27-ea < 27.
    """
    width = max(len(a.numbers), len(b.numbers))
    a_nums = a.numbers + (0,) * (width - len(a.numbers))
    b_nums = b.numbers + (0,) * (width - len(b.numbers))
    if a_nums != b_nums:
        return -1 if a_nums < b_nums else 1
    return _compare_pre(a.pre, b.pre)


def omits_required_update(actual, minimum):
    """True when actual matches the minimum as far as it goes but stops short.

    "21" against a minimum of 21.0.13.1 names the feature release only, so it
    can't show which 21 update is in use.
    """
    k = len(actual.numbers)
    return (
        actual.pre is None
        and k < len(minimum.numbers)
        and actual.numbers == minimum.numbers[:k]
        and any(minimum.numbers[k:])
    )


def _parse_or_error(value, label):
    try:
        return parse_java_version(value), None
    except ValueError as e:
        shown = f'"{value}"' if isinstance(value, str) else json.dumps(value, default=str)
        return None, f"{label} {shown} {e}"


def check_min_java_version(min_version=None, node=None):
    """Check that the Java version in build config meets the minimum."""
    if min_version is None:
        min_version = variable_or_default("min_java_version", "17")

    c = Check("min-java-version", "Ensures Java version meets minimum", node=node)
    with c:
        java = c.get_node(".lang.java")
        if not java.exists():
            c.skip("Not a Java project")
        project_exists_node = java.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Java project detected in this component")

        version_node = java.get_node(".version")
        if not version_node.exists():
            c.skip("Java version not detected in build config")

        minimum, min_error = _parse_or_error(min_version, "min_java_version")
        actual, actual_error = _parse_or_error(version_node.get_value(), "Java version")

        if min_error:
            c.fail(min_error)
        elif actual_error:
            c.fail(actual_error)
        elif omits_required_update(actual, minimum):
            c.fail(
                f"Java version {actual.text} does not specify an update release, "
                f"so it cannot be shown to meet minimum {minimum.text}"
            )
        else:
            c.assert_true(
                compare_java_versions(actual, minimum) >= 0,
                f"Java version {actual.text} is below minimum {minimum.text}. "
                f"Update your build config to target Java {minimum.text} or newer.",
            )
    return c


if __name__ == "__main__":
    check_min_java_version()
