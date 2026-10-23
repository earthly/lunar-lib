"""Parsing and matching for the max-severity `exempt_findings` input.

An exemption records that one vulnerability in one exact package version has
been reviewed and accepted. It never turns a finding into a pass: findings that
are not exempt still fail, and the check resolves to `skip`, naming what was
exempted, only when every finding that would have failed was exempted.
"""

import fnmatch


class ExemptionConfigError(ValueError):
    """A malformed `exempt_findings` value.

    Raised rather than skipped so a typo can never read as "exempt everything".
    """


class Exemption:
    """One `<id> <package>@<version> [<image-glob> ...]` entry."""

    def __init__(self, vuln_id, package, version, images):
        self.vuln_id = vuln_id
        self.package = package
        self.version = version
        self.images = images

    def __str__(self):
        text = f"{self.vuln_id} {self.package}@{self.version}"
        if self.images:
            text += " " + " ".join(self.images)
        return text

    def matches(self, vuln_id, package, version, image):
        if (vuln_id or "").upper() != self.vuln_id.upper():
            return False
        if package != self.package or version != self.version:
            return False
        if not self.images:
            return True
        # A finding with no image recorded cannot be shown to be in scope.
        return bool(image) and any(fnmatch.fnmatchcase(image, g) for g in self.images)


def parse_exempt_findings(raw):
    """Parse `exempt_findings`: entries separated by newlines or commas, each
    `<id> <package>@<version>` optionally followed by image globs. A `#`
    comments out the rest of its line, so the rationale can sit next to the
    entry it explains; comments are stripped before splitting on commas.

    Raises ExemptionConfigError on anything else.
    """
    entries = []
    for line in raw.splitlines():
        entries.extend(line.split("#", 1)[0].split(","))

    exemptions = []
    for entry in entries:
        tokens = entry.split()
        if not tokens:
            continue
        # rpartition: npm scopes start with '@', versions never contain one.
        package, sep, version = tokens[1].rpartition("@") if len(tokens) > 1 else ("", "", "")
        if not sep or not package or not version:
            raise ExemptionConfigError(
                "exempt_findings: expected '<id> <package>@<version> [<image-glob> ...]', "
                f"got {entry.strip()!r}"
            )
        exemptions.append(Exemption(tokens[0], package, version, tokens[2:]))

    return exemptions


def find_exemption(exemptions, vuln_id, package, version, image):
    for e in exemptions:
        if e.matches(vuln_id, package, version, image):
            return e
    return None


def format_exemptions(exemptions, limit=5):
    """Render the entries that matched, each once, for a check message."""
    unique = []
    for e in exemptions:
        if e not in unique:
            unique.append(e)
    shown = "; ".join(str(e) for e in unique[:limit])
    if len(unique) > limit:
        shown += f" (and {len(unique) - limit} more)"
    return shown
