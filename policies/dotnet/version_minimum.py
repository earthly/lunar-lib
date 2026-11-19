"""Minimum versions for the language version checks: one version, or one per release line.

The hub packages only a policy's own directory, so every policy that uses this
module carries an identical copy. scripts/validate_shared_modules.py fails the
lint when the copies differ: change one, copy it to all.
"""

import json
import re
from typing import NamedTuple, Optional

# 20, v20.11.0, 3.13.0rc1, 1.23rc1, 2.0.0-Beta1, 9.0.100-preview.7.24407.12,
# 8.1.2-1ubuntu2.19 (a distribution's package revision, ignored) and 3.12.0+
# (build metadata, ignored). A trailing wildcard names its line: 20.x, 8.0.x
# and 1.9.+ read as 20, 8.0 and 1.9.
_VERSION = re.compile(
    r"[vV]?(?P<num>\d+(?:\.\d+)*)"
    r"(?:-?(?P<pre>[A-Za-z][0-9A-Za-z.-]*))?"
    r"(?:-\d[0-9A-Za-z.+~:-]*)?"
    r"(?:\+[0-9A-Za-z.+~-]*)?"
)
_WILDCARD = re.compile(r"(?:\.[xX*+]|\+)+$")
_JSON_TYPES = {bool: "boolean", type(None): "null", dict: "object", list: "array"}


class Version(NamedTuple):
    text: str
    numbers: tuple
    pre: Optional[str]  # pre-release identifier, e.g. "rc1"


def _shown(value):
    return f'"{value}"' if isinstance(value, str) else json.dumps(value, default=str)


def _pre_key(pre):
    # Case-insensitive, with numbers compared as numbers: rc2 < rc10, beta1 < RC1.
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.lower()) for t in re.findall(r"\d+|[A-Za-z]+", pre)]


def compare_versions(a, b):
    """Return a negative number, zero or a positive number as a <, ==, > b.

    Missing trailing numbers count as zero, so 3.12 == 3.12.0. On equal numbers
    a pre-release sorts before the release: 3.13.0rc1 < 3.13.0.
    """
    width = max(len(a.numbers), len(b.numbers))
    a_nums = a.numbers + (0,) * (width - len(a.numbers))
    b_nums = b.numbers + (0,) * (width - len(b.numbers))
    if a_nums != b_nums:
        return -1 if a_nums < b_nums else 1
    if a.pre == b.pre:
        return 0
    if a.pre is None or b.pre is None:
        return 1 if a.pre is None else -1
    a_key, b_key = _pre_key(a.pre), _pre_key(b.pre)
    return (a_key > b_key) - (a_key < b_key)


class Runtime:
    """How a language numbers its versions and release lines.

    line_length is how many numbers name a release line: 1 for Node.js (20),
    2 for Python (3.12). With feature_bands, the last of them is a .NET SDK
    feature band: 8.0.404 is on line 8.0.4xx. normalize, if given, rewrites
    the text before it is parsed.
    """

    def __init__(self, name, line_length, forms, feature_bands=False, normalize=None):
        self.name = name
        self.line_length = line_length
        self.forms = forms
        self.feature_bands = feature_bands
        self.normalize = normalize

    def parse(self, value):
        """Parse a version into a Version; raise ValueError if it isn't one."""
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            kind = _JSON_TYPES.get(type(value), type(value).__name__)
            raise ValueError(f"must be a string such as \"{self.forms.split(',')[0]}\", got {kind}")
        text = str(value).strip()
        m = _VERSION.fullmatch(_WILDCARD.sub("", self.normalize(text) if self.normalize else text))
        if not m:
            raise ValueError(f"is not a recognized version format; expected a form like {self.forms}")
        return Version(text, tuple(int(n) for n in m["num"].split(".")), m["pre"])

    def line(self, version, length=None):
        """The release line of version, or its first length numbers."""
        line = (version.numbers + (0,) * self.line_length)[: self.line_length]
        if self.feature_bands:
            line = line[:-1] + (line[-1] // 100,)
        return line[:length]

    def line_text(self, line):
        if self.feature_bands and len(line) == self.line_length:
            return ".".join(str(n) for n in line[:-1]) + f".{line[-1]}xx"
        return ".".join(str(n) for n in line)


class Minimum:
    """A minimum version, or one minimum per release line.

    A version is held to the minimum listed for its release line, or to the
    lowest one if its line is older than every listed line. A line between
    listed ones (3.11 when 3.10 and 3.12 are listed) has no minimum and fails.
    A line newer than every listed one passes, so a single minimum keeps
    meaning "this version or newer". An entry with fewer numbers than a line,
    such as 8.0 for .NET or 3 for Python, covers every line that starts with it.
    """

    def __init__(self, runtime, floors):
        self.runtime = runtime
        self.floors = sorted(floors, key=self._line)  # lines never overlap, so tuple order is safe
        self.text = ", ".join(f.text for f in self.floors)
        self._depth = max(len(self._line(f)) for f in self.floors)

    def _line(self, floor):
        return self.runtime.line(floor, min(self.runtime.line_length, len(floor.numbers)))

    def describe(self):
        if len(self.floors) == 1:
            return f"minimum {self.text}"
        return f"the minimum for its release line ({self.text})"

    def line_text(self, version):
        """version's release line, named as precisely as the listed lines."""
        return self.runtime.line_text(self.runtime.line(version, self._depth))

    def match(self, version):
        """Return (floor, unlisted): the minimum version is held to, or None when
        its line is newer than every listed line; unlisted is True when its line
        falls between two listed lines."""
        for i, floor in enumerate(self.floors):
            line = self._line(floor)
            own = self.runtime.line(version, len(line))
            if own == line or (own < line and i == 0):
                return floor, False
            if own < line:
                return None, True
        return None, False

    def problem(self, version):
        """Return why version misses the minimum, or None if it meets it."""
        floor, unlisted = self.match(version)
        if unlisted:
            return f"{self.runtime.name} {version.text} is on release line {self.line_text(version)}, which has no listed minimum"
        if floor is not None and compare_versions(version, floor) < 0:
            return f"{self.runtime.name} {version.text} is below minimum {floor.text}"
        return None


def parse_minimum(value, runtime):
    """Parse a minimum version input into a Minimum; raise ValueError if unsupported.

    The value is one version ("3.12") or one per release line, separated by
    commas, spaces or newlines ("3.12.8, 3.13.1"), optionally as a JSON-style
    array. A # comments out the rest of its line.
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
            return Minimum(runtime, [runtime.parse(entries[0])])
        except ValueError as e:
            raise ValueError(f"{_shown(value)} {e}") from None

    floors = []
    for entry in entries:
        try:
            floor = runtime.parse(entry)
        except ValueError as e:
            raise ValueError(f'entry "{entry}" {e}') from None
        line = runtime.line(floor, len(floor.numbers))
        for other in floors:
            other_line = runtime.line(other, len(other.numbers))
            shared = min(len(line), len(other_line), runtime.line_length)
            if line[:shared] == other_line[:shared]:
                named = runtime.line_text(runtime.line(floor, shared))
                raise ValueError(f"lists {runtime.name} {named} twice: {other.text} and {floor.text}")
        floors.append(floor)
    return Minimum(runtime, floors)


def check_build_version(c, raw, minimum, advice=""):
    """Fail c unless a version read from a build file meets its minimum.

    advice is appended to a below-minimum failure; {floor} names the minimum.
    """
    name = minimum.runtime.name
    try:
        actual = minimum.runtime.parse(raw)
    except ValueError as e:
        c.fail(f"{name} version {_shown(raw)} {e}")
        return
    floor, unlisted = minimum.match(actual)
    if unlisted:
        c.fail(
            f"{name} version {actual.text} is on release line {minimum.line_text(actual)}, "
            f"which has no listed minimum ({minimum.text})."
        )
        return
    below = floor is not None and compare_versions(actual, floor) < 0
    c.assert_true(
        not below,
        f"{name} version {actual.text} is below minimum {floor.text}.{advice.format(floor=floor.text)}" if below else "",
    )


def report_ci_versions(c, cmds, minimum, skip_unrecorded=False):
    """Fail c with a summary plus one finding per distinct problem among the recorded commands.

    A command with no recorded version fails unless skip_unrecorded. Grouping
    by problem reports a runtime that ran many commands once.
    """
    name = minimum.runtime.name
    problems = {}
    for entry in cmds or []:
        entry = entry if isinstance(entry, dict) else {}
        raw = entry.get("version")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            if skip_unrecorded:
                continue
            problem = f"No {name} version recorded"
        else:
            try:
                problem = minimum.problem(minimum.runtime.parse(raw))
            except ValueError as e:
                problem = f"{name} version {_shown(raw)} {e}"
        if problem:
            problems.setdefault(problem, []).append(entry.get("cmd") or "unknown command")

    c.assert_true(not problems, f"CI ran {name} that does not meet {minimum.describe()}")
    for problem, commands in problems.items():
        count = f"{len(commands)} commands, e.g." if len(commands) > 1 else "command"
        c.fail(f"{problem} ({count} '{commands[0]}')")
