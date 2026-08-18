#!/usr/bin/env python3
"""Parse package-manager configuration into normalized registry entries.

Reads a newline-separated list of file paths on stdin and writes the
`.dependencies` Component JSON object to stdout.

Only registry locations are emitted. Credentials that live alongside them
(`_authToken` in .npmrc, <password> in settings.xml, userinfo in a URL) are
never emitted.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None


# Each ecosystem's public default — what a build resolves from when the
# repository declares no registry of its own.
ECOSYSTEM_DEFAULTS = {
    "npm": "https://registry.npmjs.org/",
    "pip": "https://pypi.org/simple",
    "maven": "https://repo.maven.apache.org/maven2",
    "gradle": "https://repo.maven.apache.org/maven2",
    "rubygems": "https://rubygems.org",
    "nuget": "https://api.nuget.org/v3/index.json",
}

# Well-known public package indexes. Used for `is_public`, which is a fact
# about the host, not a judgement about whether it is allowed.
PUBLIC_HOSTS = {
    "registry.npmjs.org",
    "registry.yarnpkg.com",
    "pypi.org",
    "pypi.python.org",
    "files.pythonhosted.org",
    "repo.maven.apache.org",
    "repo1.maven.org",
    "repo2.maven.org",
    "oss.sonatype.org",
    "s01.oss.sonatype.org",
    "jcenter.bintray.com",
    "plugins.gradle.org",
    "maven.google.com",
    "dl.google.com",
    "jitpack.io",
    "rubygems.org",
    "api.nuget.org",
    "www.nuget.org",
}

# Gradle repository shorthands that resolve to a known public host.
GRADLE_SHORTHANDS = {
    "mavenCentral": "https://repo.maven.apache.org/maven2",
    "jcenter": "https://jcenter.bintray.com",
    "google": "https://maven.google.com",
    "gradlePluginPortal": "https://plugins.gradle.org/m2",
    "mavenLocal": None,  # local filesystem, not a registry
}

ALL_ECOSYSTEMS = list(ECOSYSTEM_DEFAULTS)


def host_of(url):
    """Return the lowercase hostname for a URL, stripping any userinfo.

    Returns None for anything that isn't a resolvable remote registry
    (relative paths, file:// URLs, unexpanded variables).
    """
    if not url:
        return None
    url = url.strip().strip("'\"")
    if not url or "${" in url or "$(" in url or url.startswith("$"):
        return None
    try:
        parts = urlsplit(url if "//" in url else "//" + url)
    except ValueError:
        return None
    if parts.scheme and parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower()
    return host or None


def clean_url(url):
    """Strip credentials out of a URL before it is recorded."""
    url = url.strip().strip("'\"")
    try:
        parts = urlsplit(url if "//" in url else "//" + url)
    except ValueError:
        return url
    if not parts.hostname:
        return url
    netloc = parts.hostname
    if parts.port:
        netloc += f":{parts.port}"
    scheme = parts.scheme or "https"
    rebuilt = f"{scheme}://{netloc}{parts.path}"
    return rebuilt.rstrip("/") or rebuilt


class Registries:
    """Accumulates registry entries and the ecosystems detected."""

    def __init__(self, ecosystems):
        self.entries = []
        self.detected = set()
        self.enabled = set(ecosystems)

    def detect(self, ecosystem):
        if ecosystem in self.enabled:
            self.detected.add(ecosystem)

    def add(self, ecosystem, url, path, kind="primary", name=None, is_default=False):
        if ecosystem not in self.enabled:
            return
        self.detected.add(ecosystem)
        host = host_of(url)
        if not host:
            return
        entry = {
            "ecosystem": ecosystem,
            "host": host,
            "url": clean_url(url),
            "path": path,
            "kind": kind,
            "is_default": is_default,
            "is_public": host in PUBLIC_HOSTS,
        }
        if name:
            entry["name"] = name
        # Same host declared twice for the same ecosystem/kind adds nothing.
        for existing in self.entries:
            if (existing["ecosystem"], existing["host"], existing["kind"],
                    existing.get("name")) == (ecosystem, host, kind, name):
                return
        self.entries.append(entry)

    def has_primary(self, ecosystem):
        return any(
            e["ecosystem"] == ecosystem and e["kind"] in ("primary", "mirror")
            for e in self.entries
        )


# --------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------

def parse_npmrc(reg, path, text):
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith((";", "#")):
            continue
        # //registry.example.com/:_authToken=... — credentials, never emitted.
        if line.startswith("//"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key == "registry":
            reg.add("npm", value, path)
        elif key.endswith(":registry"):
            scope = key[: -len(":registry")]
            reg.add("npm", value, path, name=scope or None)


def parse_pip_conf(reg, path, text):
    key = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].split(";", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("["):
            key = None
            continue
        if "=" in line and not raw[:1].isspace():
            name, _, value = line.partition("=")
            key = name.strip().replace("_", "-").lower()
            value = value.strip()
        elif key and raw[:1].isspace():
            value = line.strip()  # continuation of a multi-value option
        else:
            continue
        if key == "index-url":
            reg.add("pip", value, path, kind="primary")
        elif key == "extra-index-url":
            for part in value.split():
                reg.add("pip", part, path, kind="extra")


def parse_requirements(reg, path, text):
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^(--index-url|-i|--extra-index-url|--find-links|-f)[=\s]+(\S+)", line)
        if not m:
            continue
        flag, url = m.group(1), m.group(2)
        kind = "primary" if flag in ("--index-url", "-i") else "extra"
        reg.add("pip", url, path, kind=kind)


def _table(obj, key):
    """`obj[key]` when it is a table, otherwise an empty one.

    A pyproject.toml is valid TOML but arbitrary shape — `[tool]` with
    `poetry = "1.9.0"` is legal and simply declares no sources. Traversing it
    with plain `.get()` chains would raise on the scalar.
    """
    value = obj.get(key) if isinstance(obj, dict) else None
    return value if isinstance(value, dict) else {}


def _array(obj, key):
    """`obj[key]` when it is an array, otherwise an empty one."""
    value = obj.get(key) if isinstance(obj, dict) else None
    return value if isinstance(value, list) else []


def parse_pyproject(reg, path, data):
    tool = _table(data, "tool")
    # Poetry: [[tool.poetry.source]] with an optional priority
    for src in _array(_table(tool, "poetry"), "source"):
        if not isinstance(src, dict):
            continue
        priority = str(src.get("priority", "")).lower()
        kind = "extra" if priority in ("supplemental", "explicit") else "primary"
        reg.add("pip", src.get("url"), path, kind=kind, name=src.get("name"))
    # uv: [[tool.uv.index]]
    for src in _array(_table(tool, "uv"), "index"):
        if isinstance(src, dict):
            kind = "primary" if src.get("default") else "extra"
            reg.add("pip", src.get("url"), path, kind=kind, name=src.get("name"))
    # PDM: [[tool.pdm.source]]
    for src in _array(_table(tool, "pdm"), "source"):
        if isinstance(src, dict):
            reg.add("pip", src.get("url"), path, name=src.get("name"))


def _xml_root(text):
    """Parse XML and drop namespaces so tags can be matched by local name."""
    root = ET.fromstring(text)
    for elem in root.iter():
        if isinstance(elem.tag, str) and "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]
    return root


def parse_pom(reg, path, text):
    root = _xml_root(text)
    sections = (
        ("repositories", "repository", "primary"),
        ("pluginRepositories", "pluginRepository", "plugin"),
    )
    for container, child, kind in sections:
        for parent in root.iter(container):
            for repo in parent.findall(child):
                url = repo.findtext("url")
                reg.add("maven", url, path, kind=kind, name=repo.findtext("id"))
    for dm in root.iter("distributionManagement"):
        for child in dm:
            url = child.findtext("url")
            reg.add("maven", url, path, kind="publish", name=child.findtext("id"))


def parse_settings_xml(reg, path, text):
    root = _xml_root(text)
    for mirrors in root.iter("mirrors"):
        for mirror in mirrors.findall("mirror"):
            reg.add("maven", mirror.findtext("url"), path, kind="mirror",
                    name=mirror.findtext("id"))
    for repos in root.iter("repositories"):
        for repo in repos.findall("repository"):
            reg.add("maven", repo.findtext("url"), path, name=repo.findtext("id"))
    for repos in root.iter("pluginRepositories"):
        for repo in repos.findall("pluginRepository"):
            reg.add("maven", repo.findtext("url"), path, kind="plugin",
                    name=repo.findtext("id"))


def parse_gradle(reg, path, text):
    # Strip comments so commented-out repositories aren't reported. The
    # lookbehind keeps `https://` from being mistaken for a line comment.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(?m)(?<!:)//.*$", "", text)
    in_plugin_block = "pluginManagement" in text

    for m in re.finditer(r"""\b(?:url|uri)\s*[=(]?\s*['"]([^'"]+)['"]""", text):
        url = m.group(1)
        kind = "plugin" if in_plugin_block and m.start() < text.find("}", text.find("pluginManagement")) else "primary"
        reg.add("gradle", url, path, kind=kind)

    for name, url in GRADLE_SHORTHANDS.items():
        if url and re.search(rf"\b{name}\s*\(\s*\)", text):
            kind = "plugin" if name == "gradlePluginPortal" else "primary"
            reg.add("gradle", url, path, kind=kind, name=name)


def parse_gemfile(reg, path, text):
    text = re.sub(r"(?m)#.*$", "", text)
    for m in re.finditer(r"""^\s*source\s+['"]([^'"]+)['"]""", text, re.M):
        reg.add("rubygems", m.group(1), path)
    # gem "x", source: "https://..."
    for m in re.finditer(r"""source:\s*['"]([^'"]+)['"]""", text):
        reg.add("rubygems", m.group(1), path, kind="extra")


def parse_nuget_config(reg, path, text):
    root = _xml_root(text)
    for sources in root.iter("packageSources"):
        for add in sources.findall("add"):
            reg.add("nuget", add.get("value"), path, name=add.get("key"))


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

# Files that prove an ecosystem is in use even when they declare no registry.
MANIFESTS = {
    "package.json": "npm",
    "pyproject.toml": "pip",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "settings.gradle": "gradle",
    "settings.gradle.kts": "gradle",
    "gemfile": "rubygems",
    "packages.config": "nuget",
}


def classify(path):
    base = os.path.basename(path)
    lower = base.lower()
    if lower == ".npmrc":
        return "npmrc"
    if lower in ("pip.conf", "pip.ini"):
        return "pip_conf"
    if lower.startswith("requirements") and lower.endswith(".txt"):
        return "requirements"
    if lower == "pyproject.toml":
        return "pyproject"
    if lower == "pom.xml":
        return "pom"
    if lower == "settings.xml":
        return "settings_xml"
    if lower in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"):
        return "gradle"
    if lower == "gemfile":
        return "gemfile"
    if lower == "nuget.config":
        return "nuget"
    if lower.endswith(".csproj"):
        return "csproj"
    if lower == "package.json":
        return "package_json"
    if lower == "packages.config":
        return "packages_config"
    return None


def handle(reg, path, kind, errors):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        errors.append({"path": path, "error": str(exc)})
        return

    try:
        if kind == "npmrc":
            reg.detect("npm")
            parse_npmrc(reg, path, text)
        elif kind == "pip_conf":
            reg.detect("pip")
            parse_pip_conf(reg, path, text)
        elif kind == "requirements":
            reg.detect("pip")
            parse_requirements(reg, path, text)
        elif kind == "pyproject":
            reg.detect("pip")
            if tomllib is not None:
                parse_pyproject(reg, path, tomllib.loads(text))
        elif kind == "pom":
            reg.detect("maven")
            parse_pom(reg, path, text)
        elif kind == "settings_xml":
            parse_settings_xml(reg, path, text)
        elif kind == "gradle":
            reg.detect("gradle")
            parse_gradle(reg, path, text)
        elif kind == "gemfile":
            reg.detect("rubygems")
            parse_gemfile(reg, path, text)
        elif kind == "nuget":
            reg.detect("nuget")
            parse_nuget_config(reg, path, text)
        elif kind in ("csproj", "packages_config"):
            reg.detect("nuget")
        elif kind == "package_json":
            reg.detect("npm")
    except Exception as exc:  # noqa: BLE001 — see below
        # These are arbitrary files from someone else's repository, so the set
        # of ways one can break a parser is not enumerable. Record the failure
        # against the file and carry on: one odd file must not take down the
        # other ecosystems in the same repo. Nothing is swallowed silently —
        # the exception type lands in .dependencies.errors[].
        errors.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})


def main():
    requested = os.environ.get("ECOSYSTEMS", "").strip()
    ecosystems = (
        [e.strip() for e in requested.split(",") if e.strip()]
        if requested
        else ALL_ECOSYSTEMS
    )
    unknown = [e for e in ecosystems if e not in ECOSYSTEM_DEFAULTS]
    if unknown:
        print(
            f"package-registries: unknown ecosystem(s): {', '.join(unknown)}. "
            f"Valid: {', '.join(ALL_ECOSYSTEMS)}",
            file=sys.stderr,
        )
        ecosystems = [e for e in ecosystems if e in ECOSYSTEM_DEFAULTS]

    reg = Registries(ecosystems)
    errors = []

    paths = [p.strip() for p in sys.stdin.read().splitlines() if p.strip()]
    for path in paths:
        kind = classify(path)
        if kind:
            handle(reg, path, kind, errors)

    # An ecosystem in use that declares no registry still resolves from its
    # public default. Record that rather than staying silent, so a repository
    # which was never pointed at an internal registry is still visible.
    for ecosystem in sorted(reg.detected):
        if not reg.has_primary(ecosystem):
            reg.add(
                ecosystem,
                ECOSYSTEM_DEFAULTS[ecosystem],
                _default_source_path(paths, ecosystem),
                is_default=True,
            )

    if not reg.detected:
        return 0

    entries = sorted(
        reg.entries, key=lambda e: (e["ecosystem"], e["host"], e["kind"], e["path"])
    )
    out = {
        "source": {"tool": "package-registries", "integration": "code"},
        "ecosystems": sorted(reg.detected),
        "registries": entries,
        "registries_used": sorted({e["host"] for e in entries}),
        "summary": {"has_public": any(e["is_public"] for e in entries)},
    }
    if errors:
        out["errors"] = errors
    json.dump(out, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")
    return 0


def _default_source_path(paths, ecosystem):
    """The manifest that proves the ecosystem is in use, for the default entry."""
    for path in paths:
        kind = classify(path)
        if kind and MANIFESTS.get(os.path.basename(path).lower()) == ecosystem:
            return path
        if ecosystem == "nuget" and kind == "csproj":
            return path
        if ecosystem == "pip" and kind in ("requirements", "pyproject"):
            return path
    return ""


if __name__ == "__main__":
    sys.exit(main())
