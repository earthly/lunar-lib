"""Unit tests for min-kotlin-version with one minimum or one per release line ("2.1.21, 2.2.20")."""

import contextlib
import io
import unittest

from lunar_policy import CheckStatus, Node

from min_kotlin_version import check_min_kotlin_version

PER_LINE = "2.1.21, 2.2.20"


def run(version, minimum=PER_LINE):
    data = {"lang": {"kotlin": {"project_exists": True, "version": version}}}
    node = Node.from_component_json(data, bundle_info={"workflows_finished": True})
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_kotlin_version(minimum, node=node)


def outcome(check):
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def leading_digits_comparison(version, minimum):
    """The comparison before: leading digits of each segment, padded; suffixes such as -RC ignored."""

    def parse(v):
        parts = []
        for seg in str(v).strip().split("."):
            digits = ""
            for ch in seg:
                if not ch.isdigit():
                    break
                digits += ch
            if digits == "":
                break
            parts.append(int(digits))
        return tuple(parts)

    actual, floor = parse(version), parse(minimum)
    width = max(len(actual), len(floor))
    return actual + (0,) * (width - len(actual)) >= floor + (0,) * (width - len(floor))


class PerLineTest(unittest.TestCase):
    def test_versions_against_a_list(self):
        for version, expected in [
            ("2.0.21", CheckStatus.FAIL),  # older than every listed line
            ("2.1.20", CheckStatus.FAIL),
            ("2.1.21", CheckStatus.PASS),
            ("2.2.0", CheckStatus.FAIL),  # a single 2.1.21 minimum passes it
            ("2.2.20", CheckStatus.PASS),
            ("2.3.0-Beta1", CheckStatus.PASS),  # newer than every listed line
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run(version)), expected)
        self.assertEqual(outcome(run("2.2.0", "2.1.21")), CheckStatus.PASS)

    def test_failure_messages(self):
        self.assertEqual(
            failures(run("2.2.0")),
            ["Kotlin version 2.2.0 is below minimum 2.2.20. Update the Kotlin plugin version to 2.2.20 or higher."],
        )
        self.assertEqual(
            failures(run("2.2.0", "2.1.21, 2.3.0")),
            ["Kotlin version 2.2.0 is on release line 2.2, which has no listed minimum (2.1.21, 2.3.0)."],
        )
        self.assertEqual(failures(run("2.2.20", "2.2.10, 2.2.20")), ["min_kotlin_version lists Kotlin 2.2 twice: 2.2.10 and 2.2.20"])

    def test_dynamic_version_names_its_line(self):
        self.assertEqual(outcome(run("2.1.+", "2.1")), CheckStatus.PASS)
        self.assertEqual(outcome(run("2.1.+")), CheckStatus.FAIL)  # 2.1, below 2.1.21


class SingleMinimumTest(unittest.TestCase):
    def test_same_results_as_before_for_release_versions(self):
        versions = ["1.7.21", "1.8.0", "1.9", "1.9.22", "1.9.x", "1.9.+", "2.0.0", "2.0.21", "2.1.21"]
        for minimum in ["1.8", "1.9", "2.0", "1.9.22", "2.1.20"]:
            for version in versions:
                with self.subTest(minimum=minimum, version=version):
                    expected = CheckStatus.PASS if leading_digits_comparison(version, minimum) else CheckStatus.FAIL
                    self.assertEqual(outcome(run(version, minimum)), expected)

    def test_pre_release_sorts_before_its_release(self):
        # 2.0.0-Beta1 passed a 2.0 minimum when its suffix was ignored.
        self.assertTrue(leading_digits_comparison("2.0.0-Beta1", "2.0"))
        self.assertEqual(
            failures(run("2.0.0-Beta1", "2.0")),
            ["Kotlin version 2.0.0-Beta1 is below minimum 2.0. Update the Kotlin plugin version to 2.0 or higher."],
        )
        self.assertEqual(outcome(run("2.0.0-Beta1", "1.9")), CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()
