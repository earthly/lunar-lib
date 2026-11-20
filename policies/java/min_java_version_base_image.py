import fnmatch
import re
from typing import NamedTuple, Optional

from lunar_policy import Check, variable_or_default

from min_java_version import (
    feature_release,
    omits_required_update,
    parse_java_minimum,
    parse_java_version,
    version_problem,
)

# One family per line: a repository pattern and the scheme that reads the Java
# version from the image. First match wins. A pattern without a registry means
# Docker Hub; `*` matches across `/`, so `*/eclipse-temurin` also matches mirrors.
DEFAULT_FAMILIES = """\
*/eclipse-temurin      temurin
*/amazoncorretto       version
*/openjdk              version
*/azul/zulu-openjdk*   version
cgr.dev/*/jre          chainguard
cgr.dev/*/jdk          chainguard
*/distroless/java*     distro
*/ubi*/openjdk-*       distro
"""

# Leading Java version of a tag: 21, 21.0.5, 8u432 or 8u432-b06; Temurin adds a build (21.0.5_11).
_TEMURIN_TAG = re.compile(r"(\d+u\d+(?:-b\d+)?|\d+(?:\.\d+)*(?:_\d+)?)(?=$|-)")
_VERSION_TAG = re.compile(r"(\d+u\d+(?:-b\d+)?|\d+(?:\.\d+)*)(?=$|[-_+])")
_CHAINGUARD_TAG = re.compile(r"(?:openjdk-)?(\d+(?:\.\d+)*)(?=$|-)")
# Distro images name the major in the repository (java21-debian12, openjdk-21-runtime).
_DISTRO_NAME = re.compile(r"(?:java|jdk|jre|openjdk)-?(\d+)")


class ImageRef(NamedTuple):
    text: str
    repository: str  # registry/path, e.g. docker.io/library/eclipse-temurin
    tag: Optional[str]
    digest: Optional[str]


def normalize_repository(name):
    """Qualify a repository like Docker does: eclipse-temurin -> docker.io/library/eclipse-temurin."""
    name = name.lower()
    first, _, rest = name.partition("/")
    if rest and ("." in first or ":" in first or first == "localhost"):
        return name
    return f"docker.io/{name}" if rest else f"docker.io/library/{name}"


def parse_image_reference(text):
    """Split an image reference into repository, tag and digest."""
    name, _, digest = text.strip().partition("@")
    tag = None
    slash = name.rfind("/")
    colon = name.rfind(":")
    if colon > slash:
        name, tag = name[:colon], name[colon + 1:]
    return ImageRef(text, normalize_repository(name), tag, digest or None)


class Family(NamedTuple):
    pattern: str
    scheme: str


SCHEMES = ("temurin", "version", "chainguard", "distro")


def parse_families(text):
    """Parse java_base_image_families: `<pattern> <scheme>` per line, `defaults` for the built-in list."""
    families = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line == "defaults":
            families.extend(parse_families(DEFAULT_FAMILIES))
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f'line "{line}" should be a repository pattern and a scheme, e.g. "*/eclipse-temurin temurin"')
        pattern, scheme = parts
        if scheme not in SCHEMES:
            raise ValueError(f'line "{line}" has unknown scheme "{scheme}"; expected one of {", ".join(SCHEMES)}')
        if not pattern.startswith("*"):
            pattern = normalize_repository(pattern)
        families.append(Family(pattern.lower(), scheme))
    if not families:
        raise ValueError("lists no image families")
    return families


def match_family(ref, families):
    return next((f for f in families if fnmatch.fnmatchcase(ref.repository, f.pattern)), None)


def image_java_version(ref, scheme):
    """Return (version text, None), or (None, why the version is unknown)."""
    if scheme == "distro":
        m = _DISTRO_NAME.search(ref.repository.rsplit("/", 1)[-1])
        if not m:
            return None, "its repository name doesn't name a Java release"
        return m.group(1), None
    if not ref.tag:
        if ref.digest:
            return None, "it is pinned by digest only, with no tag naming a Java version"
        return None, "it has no tag (an unset ARG or an implicit latest)"
    pattern = {"temurin": _TEMURIN_TAG, "version": _VERSION_TAG, "chainguard": _CHAINGUARD_TAG}[scheme]
    m = pattern.match(ref.tag)
    if not m:
        return None, f'its tag "{ref.tag}" doesn\'t name a Java version'
    # Temurin's _11 is the build number: 21.0.5_11 is 21.0.5+11.
    return m.group(1).replace("_", "+"), None


def evaluate(ref, family, minimum):
    """Return ("fail" | "unknown" | "pass", message) for one runtime base image."""
    text, unknown = image_java_version(ref, family.scheme)
    if unknown:
        return "unknown", f"'{ref.text}' is a Java base image, but {unknown}"
    try:
        actual = parse_java_version(text)
    except ValueError:
        return "unknown", f"'{ref.text}' names Java {text}, which isn't a recognized version"
    if minimum.unlisted(actual):
        return "fail", (
            f"'{ref.text}' runs Java {text}, on feature release {feature_release(actual)}, "
            f"which has no listed minimum ({minimum.text})"
        )
    floor = minimum.floor_for(actual)
    # A floating 21 or 21-jre tag, or a distro image's java21, could be any 21 update.
    if floor is not None and omits_required_update(actual, floor):
        return "unknown", f"'{ref.text}' names only Java {text}, not which update, so it can't show {floor.text}"
    problem = version_problem(actual, minimum)
    if problem:
        return "fail", f"'{ref.text}': {problem}"
    return "pass", ""


def check_min_java_version_base_image(min_version=None, families_text=None, node=None):
    """Check the Java base image of each Dockerfile's runtime (final) stage against the minimum."""
    if min_version is None:
        min_version = variable_or_default("min_java_version_base_image", "17")
    if families_text is None:
        families_text = variable_or_default("java_base_image_families", "") or "defaults"

    c = Check("min-java-version-base-image", "Ensures Java runtime base images meet the minimum", node=node)
    with c:
        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            c.skip("No Dockerfiles found")

        try:
            minimum = parse_java_minimum(min_version)
        except ValueError as e:
            c.fail(f"min_java_version_base_image {e}")
            return c
        try:
            families = parse_families(families_text)
        except ValueError as e:
            c.fail(f"java_base_image_families {e}")
            return c

        results = []
        for definition in definitions.get_value() or []:
            if not isinstance(definition, dict) or not definition.get("valid"):
                continue
            stage = definition.get("final_stage") or {}
            reference = stage.get("resolved_base_image") or stage.get("base_image")
            if not reference:
                continue
            ref = parse_image_reference(reference)
            family = match_family(ref, families)
            if family is None:
                continue
            verdict, message = evaluate(ref, family, minimum)
            results.append((verdict, f"{definition.get('path', 'Dockerfile')}: {message}"))

        if not results:
            c.skip("No Dockerfile's runtime stage builds on a configured Java base image family")
        failed = [m for v, m in results if v == "fail"]
        unknown = [m for v, m in results if v == "unknown"]
        if unknown and not failed:
            # Unknown is not a pass: a floating or major-only tag proves no update.
            c.skip("; ".join(unknown))
        c.assert_true(not failed, f"Java runtime base images don't meet {minimum.describe()}")
        for message in failed:
            c.fail(message)
    return c


if __name__ == "__main__":
    check_min_java_version_base_image()
