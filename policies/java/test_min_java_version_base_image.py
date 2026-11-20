"""Unit tests for min-java-version-base-image.

The check reads each Dockerfile's runtime (final) stage base image from the
docker collector (`.containers.definitions[].final_stage.resolved_base_image`),
matches it against the configured image families and compares the Java version
the family's scheme reads from it against `min_java_version_base_image`.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_java_version_base_image import (
    DEFAULT_FAMILIES,
    check_min_java_version_base_image,
    image_java_version,
    match_family,
    parse_families,
    parse_image_reference,
)

DIGEST = "sha256:" + "0" * 64
ECR = "123456789012.dkr.ecr.us-east-1.amazonaws.com"


def dockerfile(resolved, path="Dockerfile", base_images=None, **stage):
    final_stage = {"base_name": None, "base_image": resolved, "resolved_base_image": resolved}
    final_stage.update(stage)
    return {"path": path, "valid": True, "base_images": base_images or [], "final_stage": final_stage}


def run(definitions, minimum="17", families=None, finished=True):
    data = {"containers": {"definitions": definitions}} if definitions is not None else {}
    node = Node.from_component_json(data, bundle_info={"workflows_finished": finished})
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_java_version_base_image(minimum, families, node=node)


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def skip_reason(check):
    return " ".join(str(r.failure_message) for r in check._results if r.result == CheckStatus.SKIPPED)


class ImageReferenceTest(unittest.TestCase):
    def test_parse(self):
        cases = {
            "eclipse-temurin:21.0.5_11-jre": ("docker.io/library/eclipse-temurin", "21.0.5_11-jre", None),
            "azul/zulu-openjdk:21": ("docker.io/azul/zulu-openjdk", "21", None),
            f"registry.example.com:5000/mirror/eclipse-temurin:21.0.5_11-jre@{DIGEST}":
                ("registry.example.com:5000/mirror/eclipse-temurin", "21.0.5_11-jre", DIGEST),
            f"eclipse-temurin@{DIGEST}": ("docker.io/library/eclipse-temurin", None, DIGEST),
            "localhost:5000/jre": ("localhost:5000/jre", None, None),
            "cgr.dev/chainguard/jre:": ("cgr.dev/chainguard/jre", "", None),
        }
        for text, (repository, tag, digest) in cases.items():
            with self.subTest(text):
                ref = parse_image_reference(text)
                self.assertEqual((ref.repository, ref.tag, ref.digest), (repository, tag, digest))


class FamiliesTest(unittest.TestCase):
    def family(self, reference, families=DEFAULT_FAMILIES):
        found = match_family(parse_image_reference(reference), parse_families(families))
        return found.scheme if found else None

    def test_default_families(self):
        cases = {
            "eclipse-temurin:21-jre": "temurin",
            f"{ECR}/dockerhub/library/eclipse-temurin:21.0.5_11-jre": "temurin",
            "amazoncorretto:21-al2023-headless": "version",
            "openjdk:17-jdk-slim": "version",
            "azul/zulu-openjdk-alpine:21-jre": "version",
            "cgr.dev/chainguard/jre:latest": "chainguard",
            "gcr.io/distroless/java21-debian12:nonroot": "distro",
            "registry.access.redhat.com/ubi9/openjdk-21-runtime:1.21": "distro",
            "maven:3.9-eclipse-temurin-21": None,
            "nginx:1.27": None,
            "eclipse-temurin-fork:21": None,
        }
        for reference, scheme in cases.items():
            with self.subTest(reference):
                self.assertEqual(self.family(reference), scheme)

    def test_custom_families_first_match_wins(self):
        families = f"{ECR}/platform/java-runtime version\ndefaults\n"
        self.assertEqual(self.family(f"{ECR}/platform/java-runtime:21.0.6-2026.11", families), "version")
        self.assertEqual(self.family("eclipse-temurin:21-jre", families), "temurin")
        # Without `defaults` only the listed families match.
        self.assertIsNone(self.family("eclipse-temurin:21-jre", f"{ECR}/platform/java-runtime version"))
        # A pattern without a registry is a Docker Hub repository.
        self.assertEqual(self.family("eclipse-temurin:21", "eclipse-temurin temurin"), "temurin")

    def test_invalid_families(self):
        for text, error in {
            "*/eclipse-temurin": "should be a repository pattern and a scheme",
            "*/eclipse-temurin zulu": 'unknown scheme "zulu"',
            "# nothing\n": "lists no image families",
        }.items():
            with self.subTest(text), self.assertRaisesRegex(ValueError, error):
                parse_families(text)


class SchemeTest(unittest.TestCase):
    def test_versions(self):
        cases = [
            ("eclipse-temurin:21.0.5_11-jre-jammy", "temurin", "21.0.5+11"),
            ("eclipse-temurin:8u432-b06-jre", "temurin", "8u432-b06"),
            ("eclipse-temurin:21-jre", "temurin", "21"),
            ("eclipse-temurin:latest", "temurin", None),
            ("eclipse-temurin:jre", "temurin", None),
            ("amazoncorretto:21.0.5-al2023", "version", "21.0.5"),
            ("amazoncorretto:8u432-al2", "version", "8u432"),
            ("openjdk:17.0.2-jdk-slim", "version", "17.0.2"),
            ("cgr.dev/acme/jre:openjdk-21.0.5", "chainguard", "21.0.5"),
            ("cgr.dev/acme/jre:openjdk-21-dev", "chainguard", "21"),
            ("cgr.dev/chainguard/jre:latest", "chainguard", None),
            ("gcr.io/distroless/java21-debian12:nonroot", "distro", "21"),
            ("registry.access.redhat.com/ubi9/openjdk-21-runtime:1.21", "distro", "21"),
            ("cgr.dev/chainguard/jre:", "chainguard", None),
            (f"eclipse-temurin@{DIGEST}", "temurin", None),
        ]
        for reference, scheme, expected in cases:
            with self.subTest(reference):
                version, unknown = image_java_version(parse_image_reference(reference), scheme)
                self.assertEqual(version, expected)
                self.assertEqual(unknown is None, expected is not None)


class CheckTest(unittest.TestCase):
    def setUp(self):
        names = ("LUNAR_VAR_min_java_version_base_image", "LUNAR_VAR_java_base_image_families")
        self._saved = {k: os.environ.pop(k, None) for k in names}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v

    def test_pinned_update_below_minimum_fails(self):
        check = run([dockerfile("eclipse-temurin:21.0.3_9-jre")], "21.0.5")
        self.assertEqual(outcome(check), CheckStatus.FAIL)
        self.assertEqual(failures(check), [
            "Java runtime base images don't meet minimum 21.0.5",
            "Dockerfile: 'eclipse-temurin:21.0.3_9-jre': Java 21.0.3+9 is below minimum 21.0.5",
        ])

    def test_pinned_update_at_minimum_passes(self):
        self.assertEqual(outcome(run([dockerfile(f"eclipse-temurin:21.0.5_11-jre@{DIGEST}")], "21.0.5")), CheckStatus.PASS)

    def test_four_part_update(self):
        # Temurin 21.0.13+9 is below the 21.0.13.1 respin; 21.0.13.1+2 meets it.
        self.assertEqual(outcome(run([dockerfile("eclipse-temurin:21.0.13_9-jre")], "21.0.13.1")), CheckStatus.FAIL)
        self.assertEqual(outcome(run([dockerfile("eclipse-temurin:21.0.13.1_2-jre")], "21.0.13.1")), CheckStatus.PASS)

    def test_floating_major_is_unknown_not_a_pass(self):
        check = run([dockerfile("eclipse-temurin:21-jre")], "21.0.13.1")
        self.assertEqual(outcome(check), CheckStatus.SKIPPED)
        self.assertIn("names only Java 21, not which update, so it can't show 21.0.13.1", skip_reason(check))

    def test_major_only_still_decides_the_release(self):
        cases = {
            "older release fails": ("eclipse-temurin:17-jre", "21.0.13.1", CheckStatus.FAIL),
            "newer than every listed release passes": ("eclipse-temurin:25-jre", "21.0.13.1", CheckStatus.PASS),
            "unlisted release fails": ("eclipse-temurin:23-jre", "21.0.13.1, 25.0.5.1", CheckStatus.FAIL),
            "major minimum passes": ("gcr.io/distroless/java21-debian12:nonroot", "21", CheckStatus.PASS),
            "distro image can't show an update": ("gcr.io/distroless/java21-debian12:nonroot", "21.0.13.1", CheckStatus.SKIPPED),
            "distro image on an older release fails": ("registry.access.redhat.com/ubi9/openjdk-17-runtime:1.21", "21", CheckStatus.FAIL),
        }
        for name, (reference, minimum, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(outcome(run([dockerfile(reference)], minimum)), expected)

    def test_unresolved_references_are_unknown(self):
        for reference in ("cgr.dev/chainguard/jre:latest", "cgr.dev/chainguard/jre:", f"eclipse-temurin@{DIGEST}"):
            with self.subTest(reference):
                self.assertEqual(outcome(run([dockerfile(reference)], "21")), CheckStatus.SKIPPED)

    def test_registry_mirror(self):
        check = run([dockerfile(f"{ECR}/dockerhub/library/eclipse-temurin:21.0.3_9-jre")], "21.0.5")
        self.assertEqual(outcome(check), CheckStatus.FAIL)

    def test_custom_image_family(self):
        golden = f"{ECR}/platform/java-runtime:21.0.6-2026.11"
        self.assertEqual(outcome(run([dockerfile(golden)], "21.0.5")), CheckStatus.SKIPPED)
        families = f"{ECR}/platform/java-runtime version\ndefaults"
        self.assertEqual(outcome(run([dockerfile(golden)], "21.0.5", families)), CheckStatus.PASS)
        self.assertEqual(outcome(run([dockerfile(golden)], "21.0.7", families)), CheckStatus.FAIL)

    def test_builder_stages_are_not_the_runtime(self):
        builder = [{"reference": "maven:3.9-eclipse-temurin-11", "image": "maven", "tag": "3.9-eclipse-temurin-11"}]
        check = run([dockerfile("nginx:1.27", base_images=builder)], "21")
        self.assertEqual(outcome(check), CheckStatus.SKIPPED)
        self.assertIn("No Dockerfile's runtime stage builds on a configured Java base image family", skip_reason(check))
        runtime = dockerfile("eclipse-temurin:21.0.5_11-jre", base_images=builder + [{"reference": "eclipse-temurin:21.0.5_11-jre"}])
        self.assertEqual(outcome(run([runtime], "21")), CheckStatus.PASS)

    def test_falls_back_to_base_image_without_resolved_field(self):
        definition = dockerfile(None, base_image="eclipse-temurin:17-jre")
        del definition["final_stage"]["resolved_base_image"]
        self.assertEqual(outcome(run([definition], "21")), CheckStatus.FAIL)

    def test_one_failing_dockerfile_fails_despite_unknown_ones(self):
        check = run([
            dockerfile("eclipse-temurin:21-jre", path="api/Dockerfile"),
            dockerfile("eclipse-temurin:21.0.3_9-jre", path="worker/Dockerfile"),
            {"path": "broken/Dockerfile", "valid": False},
        ], "21.0.5")
        self.assertEqual(outcome(check), CheckStatus.FAIL)
        self.assertEqual(len(failures(check)), 2)
        self.assertIn("worker/Dockerfile", failures(check)[1])

    def test_no_dockerfiles(self):
        self.assertEqual(outcome(run(None)), CheckStatus.SKIPPED)
        self.assertEqual(run(None, finished=False).status, CheckStatus.PENDING)

    def test_invalid_inputs_fail(self):
        check = run([dockerfile("eclipse-temurin:21-jre")], "21.x")
        self.assertEqual(outcome(check), CheckStatus.FAIL)
        self.assertTrue(failures(check)[0].startswith("min_java_version_base_image"))
        check = run([dockerfile("eclipse-temurin:21-jre")], "21", "*/eclipse-temurin zulu")
        self.assertTrue(failures(check)[0].startswith("java_base_image_families"))

    def test_inputs_from_environment(self):
        os.environ["LUNAR_VAR_min_java_version_base_image"] = "21.0.5"
        os.environ["LUNAR_VAR_java_base_image_families"] = f"{ECR}/platform/java-runtime version"
        node = Node.from_component_json(
            {"containers": {"definitions": [dockerfile(f"{ECR}/platform/java-runtime:21.0.3")]}},
            bundle_info={"workflows_finished": True},
        )
        with contextlib.redirect_stdout(io.StringIO()):
            check = check_min_java_version_base_image(node=node)
        self.assertEqual(outcome(check), CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
