"""Unit tests for one minimum per feature release.

`min_java_version` and `min_java_version_cicd` take one version ("21.0.13.1")
or one per feature release ("21.0.13.1, 25.0.5.1, 27.0.1.1"). Each version is
held to the minimum for its own feature release, so a vulnerable 25.0.5 can't
pass just because it is newer than 21.0.13.1.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_java_version import (
    check_min_java_version,
    compare_java_versions,
    parse_java_minimum,
    parse_java_version,
    version_problem,
)
from min_java_version_cicd import check_min_java_version_cicd

PER_RELEASE = "21.0.13.1, 25.0.5.1, 27.0.1.1"
SUMMARY = "CI ran Java that does not meet the minimum for its feature release (21.0.13.1, 25.0.5.1, 27.0.1.1)"


def node_for(java, finished=True):
    data = {"lang": {"java": java}} if java is not None else {}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def java(target=None, ci_versions=None):
    data = {}
    if target is not None:
        data.update({"project_exists": True, "build_systems": ["maven"], "version": target})
    if ci_versions is not None:
        data["cicd"] = {"cmds": [{"cmd": f"java -jar app-{i}.jar", "version": v} for i, v in enumerate(ci_versions)]}
    return data


def run_build(data, minimum=PER_RELEASE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_java_version(minimum, node=node_for(data, finished))


def run_ci(data, minimum=PER_RELEASE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_java_version_cicd(minimum, node=node_for(data, finished))


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def messages(check):
    return " | ".join(r.failure_message or "" for r in check._results)


class ParseJavaMinimumTest(unittest.TestCase):
    def test_one_version_is_one_minimum(self):
        for value, text in [("21.0.13.1", "21.0.13.1"), (" 17 ", "17"), (17, "17"), ("8u202", "8u202")]:
            with self.subTest(value=value):
                minimum = parse_java_minimum(value)
                self.assertEqual((minimum.text, minimum.describe()), (text, f"minimum {text}"))

    def test_list_forms(self):
        for value in [
            "21.0.13.1, 25.0.5.1, 27.0.1.1",
            "21.0.13.1 25.0.5.1 27.0.1.1",
            "27.0.1.1,21.0.13.1,25.0.5.1",  # any order
            "[21.0.13.1, 25.0.5.1, 27.0.1.1]",
            '["21.0.13.1", "25.0.5.1", "27.0.1.1"]',
            "21.0.13.1  # first fixed 21 update\n25.0.5.1\n# 26 is end of life\n27.0.1.1\n",
        ]:
            with self.subTest(value=value):
                minimum = parse_java_minimum(value)
                self.assertEqual(minimum.text, "21.0.13.1, 25.0.5.1, 27.0.1.1")
                self.assertEqual(minimum.describe(), "the minimum for its feature release (21.0.13.1, 25.0.5.1, 27.0.1.1)")

    def test_legacy_and_build_forms_name_their_feature_release(self):
        minimum = parse_java_minimum("8u461, 11.0.29+7, 1.7.0_80, 21.0.13.1+4-LTS")
        self.assertEqual(minimum.text, "1.7.0_80, 8u461, 11.0.29+7, 21.0.13.1+4-LTS")

    def test_invalid_values_raise(self):
        for value, error in [
            ("21.0.13.1, 25.x", 'entry "25.x" is not a recognized version format'),
            ("21.0.13.1, 21.0.14", "lists Java 21 twice: 21.0.13.1 and 21.0.14"),
            ("1.8.0_461, 8u471", "lists Java 8 twice: 1.8.0_461 and 8u471"),
            ("", '"" is not a recognized version format'),
            ("[]", '"[]" is not a recognized version format'),
            ("# none yet", '"# none yet" is not a recognized version format'),
            ('"21"', 'is not a recognized version format'),  # quotes only come off inside [...]
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as e:
                    parse_java_minimum(value)
                self.assertIn(error, str(e.exception))


class SingleMinimumCompatibilityTest(unittest.TestCase):
    """A single minimum keeps meaning "this version or newer", whatever the release."""

    VERSIONS = [
        "1.7.0_80", "1.8", "8u191", "1.8.0_512", "11", "11.0.29", "17", "17.0.2", "17.0.21.1",
        "21", "21.0.5", "21.0.13", "21.0.13.0.3", "21.0.13.1", "21.0.14", "22.0.2", "23.0.2",
        "25", "25.0.5", "25.0.5.1", "27-ea", "27", "27.0.1", "28", "28-ea",
    ]

    def test_one_entry_matches_a_plain_comparison(self):
        for raw_min in ["11", "17", "21", "21.0.13.1", "1.8.0_202", "8u500", "25.0.5.1", "27-ea"]:
            minimum = parse_java_minimum(raw_min)
            for raw in self.VERSIONS:
                with self.subTest(minimum=raw_min, version=raw):
                    version = parse_java_version(raw)
                    meets = compare_java_versions(version, parse_java_version(raw_min)) >= 0
                    self.assertEqual(version_problem(version, minimum) is None, meets)


class PerReleaseCicdTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("LUNAR_VAR_min_java_version_cicd", None)

    def tearDown(self):
        os.environ.pop("LUNAR_VAR_min_java_version_cicd", None)
        if self._saved is not None:
            os.environ["LUNAR_VAR_min_java_version_cicd"] = self._saved

    def test_regression_vulnerable_newer_release_fails(self):
        # One minimum passes 25.0.5 and 27.0.1 because they are newer than 21.0.13.1.
        data = java(ci_versions=["25.0.5", "27.0.1"])
        self.assertEqual(outcome(run_ci(data, "21.0.13.1")), CheckStatus.PASS)
        c = run_ci(data)
        self.assertEqual(
            failures(c),
            [
                SUMMARY,
                "Java 25.0.5 is below minimum 25.0.5.1 (command 'java -jar app-0.jar')",
                "Java 27.0.1 is below minimum 27.0.1.1 (command 'java -jar app-1.jar')",
            ],
        )

    def test_each_release_meets_its_own_minimum(self):
        c = run_ci(java(ci_versions=["21.0.13.1", "21.0.14", "25.0.5.1", "25.0.6", "27.0.1.1", "27.0.2"]))
        self.assertEqual(outcome(c), CheckStatus.PASS, messages(c))

    def test_release_between_listed_ones_fails(self):
        for version in ["22.0.2", "23.0.2", "24.0.2", "26.0.1"]:
            with self.subTest(version=version):
                c = run_ci(java(ci_versions=[version]))
                release = version.split(".")[0]
                self.assertEqual(
                    failures(c),
                    [SUMMARY, f"Java {version} is on feature release {release}, which has no listed minimum (command 'java -jar app-0.jar')"],
                )

    def test_release_older_than_every_listed_one_fails(self):
        for version in ["17.0.21.1", "1.8.0_512"]:
            with self.subTest(version=version):
                c = run_ci(java(ci_versions=[version]))
                self.assertIn(f"Java {version} is below minimum 21.0.13.1 (command 'java -jar app-0.jar')", failures(c))

    def test_release_newer_than_every_listed_one_passes(self):
        # Like a single minimum: a release that ships after the fix includes it.
        c = run_ci(java(ci_versions=["28", "28.0.1"]))
        self.assertEqual(outcome(c), CheckStatus.PASS, messages(c))

    def test_minimum_release_with_a_fixed_update_on_every_release_since(self):
        every = "21.0.13.1, 22.0.2, 23.0.2, 24.0.2, 25.0.5.1, 26.0.1, 27.0.1.1"
        some = "21.0.13.1, 22, 23, 24, 25.0.5.1, 26, 27.0.1.1"  # bare releases take any update
        for version, with_every, with_some in [
            ("17.0.21.1", CheckStatus.FAIL, CheckStatus.FAIL),
            ("21.0.13", CheckStatus.FAIL, CheckStatus.FAIL),
            ("22.0.1", CheckStatus.FAIL, CheckStatus.PASS),
            ("23.0.2", CheckStatus.PASS, CheckStatus.PASS),
            ("25.0.5", CheckStatus.FAIL, CheckStatus.FAIL),
            ("26.0.0", CheckStatus.FAIL, CheckStatus.PASS),
            ("28.0.1", CheckStatus.PASS, CheckStatus.PASS),
        ]:
            with self.subTest(version=version):
                data = java(ci_versions=[version])
                self.assertEqual((outcome(run_ci(data, every)), outcome(run_ci(data, some))), (with_every, with_some))

    def test_mixed_patched_and_vulnerable_fails_only_the_vulnerable_versions(self):
        c = run_ci(java(ci_versions=["21.0.13.1", "25.0.5", "21.0.13.1", "25.0.5.1", "23.0.2", "25.0.5", "27.0.1.1"]))
        self.assertEqual(
            failures(c),
            [
                SUMMARY,
                "Java 25.0.5 is below minimum 25.0.5.1 (2 commands, e.g. 'java -jar app-1.jar')",
                "Java 23.0.2 is on feature release 23, which has no listed minimum (command 'java -jar app-4.jar')",
            ],
        )

    def test_vendor_version_strings(self):
        # What `java -version` reports, as the java collector records it.
        for version, expected in [
            ("21.0.13.1", CheckStatus.PASS),  # Corretto, Zulu, Microsoft and Oracle builds of the fix
            ("21.0.13.1+2-LTS", CheckStatus.PASS),  # build numbers differ by vendor and are ignored
            ("21.0.13.1+4-LTS", CheckStatus.PASS),
            ("21.0.13", CheckStatus.FAIL),  # Temurin before its fix
            ("21.0.13+9-LTS", CheckStatus.FAIL),
            ("21.0.13.0.3", CheckStatus.FAIL),  # IBM Semeru numbers its 21.0.13 builds 21.0.13.0.x
            ("25.0.5", CheckStatus.FAIL),
            ("25.0.5.1", CheckStatus.PASS),
        ]:
            with self.subTest(version=version):
                c = run_ci(java(ci_versions=[version]))
                self.assertEqual(outcome(c), expected, messages(c))
        legacy = java(ci_versions=["1.8.0_512", "8u471"])
        self.assertEqual(outcome(run_ci(legacy, "8u461, 21.0.13.1")), CheckStatus.PASS)
        c = run_ci(legacy, "1.8.0_512, 21.0.13.1")
        self.assertEqual(failures(c)[1:], ["Java 8u471 is below minimum 1.8.0_512 (command 'java -jar app-1.jar')"])

    def test_missing_or_incomplete_version_evidence(self):
        for entry, problem in [
            ({"cmd": "java -jar app.jar", "version": ""}, "No Java version recorded (command 'java -jar app.jar')"),
            ({"cmd": "java -jar app.jar"}, "No Java version recorded (command 'java -jar app.jar')"),
            # A JDK reports its full version, so "21" is the 21 GA release.
            ({"cmd": "java -jar app.jar", "version": "21"}, "Java 21 is below minimum 21.0.13.1 (command 'java -jar app.jar')"),
        ]:
            with self.subTest(entry=entry):
                c = run_ci({"cicd": {"cmds": [entry, {"cmd": "java -version", "version": "25.0.5.1"}]}})
                self.assertEqual(failures(c), [SUMMARY, problem])

    def test_no_java_in_ci_skips_and_pends_while_collecting(self):
        self.assertEqual(outcome(run_ci(java(target="21"))), CheckStatus.SKIPPED)
        self.assertEqual(outcome(run_ci(java(ci_versions=[]))), CheckStatus.SKIPPED)
        self.assertEqual(outcome(run_ci(None, finished=False)), CheckStatus.PENDING)

    def test_list_from_policy_input(self):
        os.environ["LUNAR_VAR_min_java_version_cicd"] = "21.0.13.1\n25.0.5.1\n27.0.1.1"
        with contextlib.redirect_stdout(io.StringIO()):
            c = check_min_java_version_cicd(node=node_for(java(ci_versions=["25.0.5"])))
        self.assertIn("Java 25.0.5 is below minimum 25.0.5.1 (command 'java -jar app-0.jar')", failures(c))

    def test_invalid_list_fails(self):
        c = run_ci(java(ci_versions=["21.0.13.1"]), "21.0.13.1, 21.0.14")
        self.assertEqual(failures(c), ["min_java_version_cicd lists Java 21 twice: 21.0.13.1 and 21.0.14"])
        c = run_ci(java(ci_versions=["21.0.13.1"]), "21.0.13.1, latest")
        self.assertIn('min_java_version_cicd entry "latest" is not a recognized version format', failures(c)[0])


class PerReleaseBuildTargetTest(unittest.TestCase):
    def test_listed_release_target_takes_its_update_from_ci(self):
        for target, ci_version, expected in [
            ("21", "21.0.13.1", CheckStatus.PASS),
            ("21", "21.0.13", CheckStatus.FAIL),
            ("21", "25.0.5", CheckStatus.FAIL),  # a target of 21 built on a vulnerable JDK 25
            ("21", "25.0.5.1", CheckStatus.PASS),
            ("25", "25.0.5.1", CheckStatus.PASS),
            ("25", "25.0.5", CheckStatus.FAIL),
            ("27", "27.0.1", CheckStatus.FAIL),
        ]:
            with self.subTest(target=target, ci_version=ci_version):
                c = run_build(java(target=target, ci_versions=[ci_version]))
                self.assertEqual(outcome(c), expected, messages(c))
        c = run_build(java(target="21", ci_versions=["25.0.5"]))
        self.assertEqual(
            failures(c),
            [
                "Java 21 in the build config doesn't show which update is in use, and CI ran Java that does not "
                "meet the minimum for its feature release (21.0.13.1, 25.0.5.1, 27.0.1.1)",
                "Java 25.0.5 is below minimum 25.0.5.1 (command 'java -jar app-0.jar')",
            ],
        )

    def test_target_without_ci_evidence_skips(self):
        for target, floor in [("21", "21.0.13.1"), ("25", "25.0.5.1")]:
            with self.subTest(target=target):
                c = run_build(java(target=target))
                self.assertEqual(outcome(c), CheckStatus.SKIPPED)
                self.assertIn(f"CI recorded no java or javac commands to compare with minimum {floor}", messages(c))

    def test_target_pends_while_ci_evidence_may_arrive(self):
        self.assertEqual(outcome(run_build(java(target="25"), finished=False)), CheckStatus.PENDING)

    def test_target_on_a_release_between_listed_ones_fails(self):
        c = run_build(java(target="23", ci_versions=["25.0.5.1"]))
        self.assertEqual(
            failures(c),
            ["Java version 23 is on feature release 23, which has no listed minimum (21.0.13.1, 25.0.5.1, 27.0.1.1)."],
        )

    def test_target_older_than_every_listed_release_fails(self):
        c = run_build(java(target="17", ci_versions=["21.0.13.1"]))
        self.assertEqual(
            failures(c),
            ["Java version 17 is below minimum 21.0.13.1. Update your build config to target Java 21 or newer."],
        )

    def test_target_newer_than_every_listed_release_passes(self):
        self.assertEqual(outcome(run_build(java(target="28"))), CheckStatus.PASS)

    def test_release_listed_without_an_update_needs_no_ci(self):
        c = run_build(java(target="21"), "21, 25.0.5.1")
        self.assertEqual(outcome(c), CheckStatus.PASS, messages(c))

    def test_explicit_update_target_is_compared_directly(self):
        c = run_build(java(target="25.0.1"))
        self.assertEqual(failures(c), ["Java version 25.0.1 is below minimum 25.0.5.1."])


class ReadmeExampleTest(unittest.TestCase):
    """Both checks with the README's per-release example, one component per row."""

    def test_components(self):
        for target, ci_versions, build, ci in [
            ("21", ["21.0.13.1"], CheckStatus.PASS, CheckStatus.PASS),
            ("21", ["21.0.13"], CheckStatus.FAIL, CheckStatus.FAIL),
            ("25", ["25.0.5"], CheckStatus.FAIL, CheckStatus.FAIL),
            ("21", ["21.0.13.1", "25.0.5"], CheckStatus.FAIL, CheckStatus.FAIL),
            ("17", ["17.0.21.1"], CheckStatus.FAIL, CheckStatus.FAIL),
            ("21", None, CheckStatus.SKIPPED, CheckStatus.SKIPPED),  # no CI/CD Tracer
            (None, ["23.0.2"], CheckStatus.SKIPPED, CheckStatus.FAIL),  # no build file
            ("27", ["27.0.1.1"], CheckStatus.PASS, CheckStatus.PASS),
        ]:
            with self.subTest(target=target, ci_versions=ci_versions):
                data = java(target=target, ci_versions=ci_versions)
                self.assertEqual((outcome(run_build(data)), outcome(run_ci(data))), (build, ci))


if __name__ == "__main__":
    unittest.main()
