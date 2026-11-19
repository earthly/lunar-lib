"""Unit tests for min-scala-version with one minimum or one per release line ("2.12.20, 2.13.16, 3.3.6")."""

import contextlib
import io
import unittest

from lunar_policy import CheckStatus, Node

from min_scala_version import check_min_scala_version

PER_LINE = "2.12.20, 2.13.16, 3.3.6"


def run(version, minimum=PER_LINE):
    data = {"lang": {"scala": {"project_exists": True, "version": version}}}
    node = Node.from_component_json(data, bundle_info={"workflows_finished": True})
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_scala_version(minimum, node=node)


def outcome(check):
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def padded_comparison(version, minimum):
    """The comparison before one minimum per release line."""
    actual, floor = (tuple(int(p) for p in str(x).split(".")) for x in (version, minimum))
    width = max(len(actual), len(floor))
    return actual + (0,) * (width - len(actual)) >= floor + (0,) * (width - len(floor))


class PerLineTest(unittest.TestCase):
    def test_versions_against_a_list(self):
        for version, expected in [
            ("2.11.12", CheckStatus.FAIL),  # older than every listed line
            ("2.12.19", CheckStatus.FAIL),
            ("2.12.20", CheckStatus.PASS),
            ("2.13.14", CheckStatus.FAIL),  # a single 2.12.20 minimum passes it
            ("2.13.16", CheckStatus.PASS),
            ("2.13", CheckStatus.FAIL),  # a binary version names no patch release
            ("3.0.2", CheckStatus.FAIL),  # between 2.13 and 3.3
            ("3.3.5", CheckStatus.FAIL),
            ("3.3.6", CheckStatus.PASS),
            ("3.7.3", CheckStatus.PASS),  # newer than every listed line
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run(version)), expected)
        self.assertEqual(outcome(run("2.13.14", "2.12.20")), CheckStatus.PASS)

    def test_failure_messages(self):
        self.assertEqual(
            failures(run("2.13.14")),
            ["Scala version 2.13.14 is below minimum 2.13.16. Update scalaVersion to 2.13.16 or higher."],
        )
        self.assertEqual(
            failures(run("3.0.2")),
            ["Scala version 3.0.2 is on release line 3.0, which has no listed minimum (2.12.20, 2.13.16, 3.3.6)."],
        )


class SingleMinimumTest(unittest.TestCase):
    def test_same_results_as_before_for_release_versions(self):
        versions = ["2.11.12", "2.12.20", "2.13", "2.13.0", "2.13.16", "3.3.0", "3.3.1", "3.3.6", "3.6.4"]
        for minimum in ["2.12", "2.13", "3.3.1", "2.13.0", "3"]:
            for version in versions:
                with self.subTest(minimum=minimum, version=version):
                    expected = CheckStatus.PASS if padded_comparison(version, minimum) else CheckStatus.FAIL
                    self.assertEqual(outcome(run(version, minimum)), expected)

    def test_pre_release_is_now_compared(self):
        # 3.6.0-RC1 didn't parse before and failed every minimum.
        self.assertEqual(outcome(run("3.6.0-RC1", "3.3.1")), CheckStatus.PASS)
        self.assertEqual(outcome(run("3.6.0-RC1", "3.6.0")), CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
