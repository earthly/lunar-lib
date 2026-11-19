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


def feature_release(version):
    """The feature release a version belongs to: 21 for 21.0.13.1, 8 for 1.8.0_202."""
    return version.numbers[0]


class JavaMinimum:
    """A minimum Java version, or one minimum per feature release.

    A version is held to the minimum listed for its feature release, or to the
    lowest one if its release is older than every listed release. A release
    between listed ones (23 when 21 and 25 are listed) has no minimum and fails.
    A release newer than every listed one passes, so a single minimum such as
    21.0.13.1 still passes any 25.
    """

    def __init__(self, floors):
        self.floors = sorted(floors, key=feature_release)
        self.text = ", ".join(f.text for f in self.floors)

    def describe(self):
        if len(self.floors) == 1:
            return f"minimum {self.text}"
        return f"the minimum for its feature release ({self.text})"

    def unlisted(self, version):
        """True when version's feature release falls between two listed releases."""
        release = feature_release(version)
        listed = [feature_release(f) for f in self.floors]
        return listed[0] < release < listed[-1] and release not in listed

    def floor_for(self, version):
        """The minimum version is held to, or None if its release is newer than every listed one."""
        return next((f for f in self.floors if feature_release(f) >= feature_release(version)), None)


def _shown(value):
    return f'"{value}"' if isinstance(value, str) else json.dumps(value, default=str)


def parse_java_minimum(value):
    """Parse a min_java_version input into a JavaMinimum; raise ValueError if unsupported.

    The value is one version ("21.0.13.1") or one per feature release, separated
    by commas, spaces or newlines ("21.0.13.1, 25.0.5.1, 27.0.1.1"), optionally
    as a JSON-style array. A # comments out the rest of its line.
    """
    entries = [value]
    if isinstance(value, str):
        text = "\n".join(line.split("#", 1)[0] for line in value.splitlines()).strip()
        bracketed = text.startswith("[") and text.endswith("]")
        if bracketed:
            text = text[1:-1]
        entries = [e.strip("\"'") if bracketed else e for e in re.split(r"[\s,]+", text)]
        entries = [e for e in entries if e] or [value]

    if len(entries) == 1:
        try:
            return JavaMinimum([parse_java_version(entries[0])])
        except ValueError as e:
            raise ValueError(f"{_shown(value)} {e}") from None

    floors = {}
    for entry in entries:
        try:
            floor = parse_java_version(entry)
        except ValueError as e:
            raise ValueError(f'entry "{entry}" {e}') from None
        release = feature_release(floor)
        if release in floors:
            raise ValueError(f"lists Java {release} twice: {floors[release].text} and {floor.text}")
        floors[release] = floor
    return JavaMinimum(floors.values())


def version_problem(actual, minimum):
    """Return why a complete version (one a JDK reported) misses the minimum, or None."""
    if minimum.unlisted(actual):
        return f"Java {actual.text} is on feature release {feature_release(actual)}, which has no listed minimum"
    floor = minimum.floor_for(actual)
    if floor is not None and compare_java_versions(actual, floor) < 0:
        return f"Java {actual.text} is below minimum {floor.text}"
    return None


def omits_required_update(actual, minimum):
    """True when a build-file version names no update ("21", "21.0") but the minimum needs one.

    Build files declare only the feature release, so "21" against 21.0.13.1
    can't show which 21 update is in use.
    """
    k = len(actual.numbers)
    return (
        actual.pre is None
        and k < 3
        and k < len(minimum.numbers)
        and actual.numbers == minimum.numbers[:k]
        and any(minimum.numbers[k:])
    )


def ci_version_problem(raw, minimum):
    """Return why one version recorded in CI misses the minimum, or None if it meets it.

    A JDK reports its full version, so a recorded "21" is 21.0.0, not an unknown update.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "No Java version recorded"
    try:
        actual = parse_java_version(raw)
    except ValueError as e:
        return f"Java version {_shown(raw)} {e}"
    return version_problem(actual, minimum)


def report_ci_versions(c, cmds, minimum, summary):
    """Fail c with summary plus one finding per distinct problem among the recorded commands.

    Grouping by problem reports a JDK that ran many commands once.
    """
    problems = {}
    for entry in cmds:
        entry = entry if isinstance(entry, dict) else {}
        problem = ci_version_problem(entry.get("version"), minimum)
        if problem:
            problems.setdefault(problem, []).append(entry.get("cmd") or "unknown command")

    c.assert_true(not problems, summary)
    for problem, commands in problems.items():
        count = f"{len(commands)} commands, e.g." if len(commands) > 1 else "command"
        c.fail(f"{problem} ({count} '{commands[0]}')")


def _check_update_from_ci(c, target, floor, minimum):
    """Take the update a feature-release build target can't show from the JDKs CI ran."""
    cmds_node = c.get_node(".lang.java.cicd.cmds")
    cmds = cmds_node.get_value() if cmds_node.exists() else None
    unknown = f"Java {target.text} in the build config doesn't show which update is in use"
    if not cmds:
        # Nothing ran in CI to compare, e.g. the CI/CD Tracer isn't installed.
        c.skip(f"{unknown}, and CI recorded no java or javac commands to compare with minimum {floor.text}")
        return
    report_ci_versions(c, cmds, minimum, f"{unknown}, and CI ran Java that does not meet {minimum.describe()}")


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

        try:
            minimum = parse_java_minimum(min_version)
        except ValueError as e:
            c.fail(f"min_java_version {e}")
            return c
        try:
            actual = parse_java_version(version_node.get_value())
        except ValueError as e:
            c.fail(f"Java version {_shown(version_node.get_value())} {e}")
            return c

        floor = minimum.floor_for(actual)
        if minimum.unlisted(actual):
            c.fail(
                f"Java version {actual.text} is on feature release {feature_release(actual)}, "
                f"which has no listed minimum ({minimum.text})."
            )
        elif floor is not None and omits_required_update(actual, floor):
            _check_update_from_ci(c, actual, floor, minimum)
        else:
            below = floor is not None and compare_java_versions(actual, floor) < 0
            # A build target takes a feature release, never an update like 21.0.13.1.
            advice = (
                f" Update your build config to target Java {feature_release(floor)} or newer."
                if below and feature_release(actual) < feature_release(floor)
                else ""
            )
            c.assert_true(not below, f"Java version {actual.text} is below minimum {floor.text}.{advice}" if below else "")
    return c


if __name__ == "__main__":
    check_min_java_version()
