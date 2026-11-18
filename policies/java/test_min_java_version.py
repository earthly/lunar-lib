"""Unit tests for min-java-version.

The check compares full Java versions, so a minimum such as 21.0.13.1 fails a
component on 21.0.5 even though both are Java 21. Major-only minimums ("17")
behave as before, and unsupported values fail explicitly instead of passing.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_java_version import (
    check_min_java_version,
    compare_java_versions,
    parse_java_version,
)


def run_check(version, minimum=None, finished=True, java=None):
    if java is None:
        java = {"project_exists": True, "build_systems": ["maven"], "version": version}
    data = {"lang": {"java": java}} if java != {} else {}
    node = Node.from_component_json(data, bundle_info={"workflows_finished": finished})
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_java_version(minimum, node=node)


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def messages(check):
    return " | ".join(r.failure_message or "" for r in check._results)


class ParseJavaVersionTest(unittest.TestCase):
    def assertParses(self, text, numbers, pre=None):
        v = parse_java_version(text)
        self.assertEqual((v.numbers, v.pre), (numbers, pre), text)

    def test_modern_dotted_versions(self):
        self.assertParses("21", (21,))
        self.assertParses("21.0.5", (21, 0, 5))
        self.assertParses("21.0.13.1", (21, 0, 13, 1))
        self.assertParses("17.0.21.0.3", (17, 0, 21, 0, 3))

    def test_build_numbers_and_optional_info_are_dropped(self):
        self.assertParses("21.0.5+11", (21, 0, 5))
        self.assertParses("21.0.5+11-LTS", (21, 0, 5))
        self.assertParses("25.0.5.1+1-LTS", (25, 0, 5, 1))
        self.assertParses("21.0.5+9-jvmci-23.1-b48", (21, 0, 5))
        self.assertParses("21+-custom", (21,))

    def test_prereleases(self):
        self.assertParses("27-ea", (27,), "ea")
        self.assertParses("27-ea+12", (27,), "ea")
        self.assertParses("21.0.6-ea+3-LTS", (21, 0, 6), "ea")
        self.assertParses("17.0.2-internal", (17, 0, 2), "internal")

    def test_legacy_java8_and_earlier(self):
        self.assertParses("1.8", (8,))
        self.assertParses("1.8.0", (8, 0))
        self.assertParses("1.8.0_202", (8, 0, 202))
        self.assertParses("1.8.0_202-b08", (8, 0, 202))
        self.assertParses("1.8.0_202-ea", (8, 0, 202), "ea")
        self.assertParses("1.8.0_202-ea-b03", (8, 0, 202), "ea")
        self.assertParses("1.7.0_80", (7, 0, 80))
        self.assertParses("1.10", (10,))  # Gradle's sourceCompatibility 1.10 is Java 10

    def test_update_release_names(self):
        self.assertParses("8u202", (8, 0, 202))
        self.assertParses("8u202-b08", (8, 0, 202))
        self.assertParses("8u202b08", (8, 0, 202))

    def test_numbers_and_surrounding_whitespace(self):
        self.assertParses(21, (21,))
        self.assertParses(1.8, (8,))
        self.assertParses(" 21.0.5 ", (21, 0, 5))

    def test_unsupported_values_raise(self):
        for value in [
            "", "abc", "latest", "17.x", "17.*", "v21", "jdk-21.0.5+11", "21.0.5_11",
            "21.", ".21", "21..0", "21+", "21.0.5+", "${java.version}", "[17,)", "17+",
            "8u", "1.8.0_", "1.8_202", "8u511b33-perf", "21 LTS",
            True, None, [], {"version": "21"},
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_java_version(value)


class CompareJavaVersionsTest(unittest.TestCase):
    def cmp(self, a, b):
        return compare_java_versions(parse_java_version(a), parse_java_version(b))

    def test_ordering(self):
        for lower, higher in [
            ("21.0.5", "21.0.13.1"),  # same major, lower update
            ("21.0.13", "21.0.13.1"),
            ("21.0.13.0.3", "21.0.13.1"),  # five-element emergency-release numbering
            ("17.0.21.1", "21"),
            ("21", "21.0.1"),
            ("1.8.0_202", "1.8.0_211"),
            ("8u191", "1.8.0_202"),
            ("1.8.0_202", "11"),
            ("27-ea", "27"),  # a pre-release sorts before its release
            ("27-ea", "27.0.1"),
            ("21.0.13.1", "21.0.14-ea"),  # but after every earlier version
            ("27-2", "27-10"),  # numeric pre-release identifiers compare as numbers
            ("27-10", "27-ea"),  # and sort before alphanumeric ones
        ]:
            with self.subTest(lower=lower, higher=higher):
                self.assertLess(self.cmp(lower, higher), 0)
                self.assertGreater(self.cmp(higher, lower), 0)

    def test_equal(self):
        for a, b in [
            ("21", "21.0.0"),  # trailing zeros are insignificant
            ("21.0.5+11-LTS", "21.0.5"),
            ("21.0.5+11", "21.0.5+9"),  # build numbers are vendor-specific and ignored
            ("1.8.0_202", "8u202"),
            ("1.8.0_202-b08", "8.0.202"),
            ("1.8", "8"),
            ("27-ea+5", "27-ea+12"),
        ]:
            with self.subTest(a=a, b=b):
                self.assertEqual(self.cmp(a, b), 0)
                self.assertEqual(self.cmp(b, a), 0)


class MinJavaVersionCheckTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("LUNAR_VAR_min_java_version", None)

    def tearDown(self):
        os.environ.pop("LUNAR_VAR_min_java_version", None)
        if self._saved is not None:
            os.environ["LUNAR_VAR_min_java_version"] = self._saved

    def assertOutcome(self, version, minimum, expected, message=None):
        c = run_check(version, minimum)
        self.assertEqual(outcome(c), expected, f"{version!r} vs minimum {minimum!r}: {messages(c)}")
        if message:
            self.assertIn(message, messages(c))

    def test_regression_same_major_lower_update_fails(self):
        # Truncating both sides to the major passed this: 21 >= 21.
        self.assertOutcome(
            "21.0.5", "21.0.13.1", CheckStatus.FAIL, "Java version 21.0.5 is below minimum 21.0.13.1"
        )
        self.assertOutcome("17.0.2", "17.0.21.1", CheckStatus.FAIL)

    def test_versions_at_or_above_an_update_minimum_pass(self):
        for version in ["21.0.13.1", "21.0.14", "21.0.13.1+1-LTS", "25", "25.0.5.1"]:
            self.assertOutcome(version, "21.0.13.1", CheckStatus.PASS)

    def test_major_only_minimum_keeps_working(self):
        for version, expected in [
            ("17", CheckStatus.PASS),
            ("17.0.2", CheckStatus.PASS),
            ("21", CheckStatus.PASS),
            ("11", CheckStatus.FAIL),
            ("1.8", CheckStatus.FAIL),
        ]:
            self.assertOutcome(version, "17", expected)

    def test_feature_release_only_cannot_meet_an_update_minimum(self):
        for version in ["21", "21.0"]:
            self.assertOutcome(
                version, "21.0.13.1", CheckStatus.FAIL, "does not specify an update release"
            )
        self.assertOutcome("21", "21.0.0", CheckStatus.PASS)  # nothing beyond the feature release is required

    def test_older_feature_release_fails_whatever_its_update(self):
        self.assertOutcome("17", "21.0.13.1", CheckStatus.FAIL, "below minimum 21.0.13.1")

    def test_legacy_versions(self):
        self.assertOutcome("1.8.0_202", "8u191", CheckStatus.PASS)
        self.assertOutcome("1.8.0_202", "1.8.0_211", CheckStatus.FAIL)
        self.assertOutcome("8u202", "1.8", CheckStatus.PASS)
        self.assertOutcome("1.8.0_202", "17", CheckStatus.FAIL)

    def test_prerelease_sorts_before_release(self):
        self.assertOutcome("27-ea", "27", CheckStatus.FAIL)
        self.assertOutcome("27", "27-ea", CheckStatus.PASS)

    def test_unparseable_version_fails(self):
        for version in ["17.x", "latest", "${java.version}"]:
            self.assertOutcome(version, "17", CheckStatus.FAIL, "is not a recognized version format")

    def test_non_string_version_fails(self):
        self.assertOutcome(True, "17", CheckStatus.FAIL, "Java version true must be a string")
        self.assertOutcome(["17"], "17", CheckStatus.FAIL, "must be a string")

    def test_numeric_version_value_is_accepted(self):
        self.assertOutcome(21, "17", CheckStatus.PASS)

    def test_unparseable_minimum_fails(self):
        for minimum in ["17.x", "latest", ""]:
            self.assertOutcome("21", minimum, CheckStatus.FAIL, "min_java_version")

    def test_default_minimum_is_17(self):
        self.assertOutcome("11", None, CheckStatus.FAIL, "below minimum 17")
        self.assertOutcome("17", None, CheckStatus.PASS)

    def test_minimum_from_policy_input(self):
        os.environ["LUNAR_VAR_min_java_version"] = "21.0.13.1"
        self.assertOutcome("21.0.5", None, CheckStatus.FAIL, "below minimum 21.0.13.1")

    def test_skips_where_there_is_no_version_to_check(self):
        self.assertEqual(outcome(run_check(None, "17", java={})), CheckStatus.SKIPPED)
        self.assertEqual(
            outcome(run_check(None, "17", java={"project_exists": False, "version": "11"})),
            CheckStatus.SKIPPED,
        )
        self.assertEqual(
            outcome(run_check(None, "17", java={"project_exists": True})), CheckStatus.SKIPPED
        )

    def test_pending_while_collection_is_running(self):
        c = run_check(None, "17", finished=False, java={})
        self.assertEqual(outcome(c), CheckStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
