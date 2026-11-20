"""Unit tests for min-version and min-version-cicd.

Both take one minimum or one per release line ("8.2.29, 8.3.27, 8.4.14"), so a
vulnerable 8.4.1 can't pass just because it is newer than 8.2.29.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_version import check_min_version
from min_version_cicd import check_min_version_cicd

PER_LINE = "8.2.29, 8.3.27, 8.4.14"
SUMMARY = "CI ran PHP that does not meet the minimum for its release line (8.2.29, 8.3.27, 8.4.14)"


def node_for(php, finished=True):
    data = {"lang": {"php": php}} if php is not None else {}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def php(constraint=None, ci_versions=None):
    data = {}
    if constraint is not None:
        data.update({"project_exists": True, "version": constraint})
    if ci_versions is not None:
        data["cicd"] = {"cmds": [{"cmd": f"php artisan task{i}", "version": v} for i, v in enumerate(ci_versions)]}
    return data


def run_build(data, minimum=PER_LINE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_version(minimum, node=node_for(data, finished))


def run_ci(data, minimum=PER_LINE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_version_cicd(minimum, node=node_for(data, finished))


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def truncated_comparison(version, minimum):
    """The CI comparison before one minimum per release line: the version cut to the minimum's length."""
    actual, floor = (tuple(int(p) for p in str(x).split(".")) for x in (version, minimum))
    return actual[: len(floor)] >= floor


class PerLineConstraintTest(unittest.TestCase):
    """min-version compares the lowest version composer.json's PHP constraint allows."""

    def test_constraints_against_a_list(self):
        for constraint, expected in [
            ("^8.1", CheckStatus.FAIL),  # older than every listed line
            ("^8.3", CheckStatus.FAIL),  # allows 8.3.0
            ("8.3.*", CheckStatus.FAIL),
            (">=8.3.27", CheckStatus.PASS),
            ("^8.2.29 || ^8.3.27", CheckStatus.PASS),
            ("^7.4 || ^8.4.14", CheckStatus.FAIL),
            ("~8.4.14", CheckStatus.PASS),
            ("^8.5", CheckStatus.PASS),  # newer than every listed line
        ]:
            with self.subTest(constraint=constraint):
                self.assertEqual(outcome(run_build(php(constraint=constraint))), expected)

    def test_failure_messages(self):
        self.assertEqual(
            failures(run_build(php(constraint="^8.3"))),
            ["PHP version ^8.3 (min 8.3) is below minimum 8.3.27. Update the PHP constraint in composer.json."],
        )
        self.assertEqual(
            failures(run_build(php(constraint="^8.3"), "8.2.29, 8.4.14")),
            ["PHP version ^8.3 (min 8.3) is on release line 8.3, which has no listed minimum (8.2.29, 8.4.14)."],
        )
        self.assertEqual(failures(run_build(php(constraint="*"))), ["Could not parse PHP version constraint: *"])

    def test_composer_style_minimum(self):
        # ^8.1 worked as a minimum before; it still means 8.1.
        for minimum in ["^8.1", "~8.1", ">=8.1", "8.1.x"]:
            with self.subTest(minimum=minimum):
                self.assertEqual(outcome(run_build(php(constraint="^8.1"), minimum)), CheckStatus.PASS)
                self.assertEqual(outcome(run_build(php(constraint="^8.0"), minimum)), CheckStatus.FAIL)

    def test_minimum_with_a_zero_patch_accepts_its_line(self):
        # Truncating made ^8.1 fail an 8.1.0 minimum.
        self.assertEqual(outcome(run_build(php(constraint="^8.1"), "8.1.0")), CheckStatus.PASS)


class PerLineCicdTest(unittest.TestCase):
    def test_vulnerable_newer_line_fails(self):
        data = php(ci_versions=["8.4.1"])
        self.assertEqual(outcome(run_ci(data, "8.2.29")), CheckStatus.PASS)
        self.assertEqual(failures(run_ci(data)), [SUMMARY, "PHP 8.4.1 is below minimum 8.4.14 (command 'php artisan task0')"])

    def test_versions_against_a_list(self):
        for version, expected in [
            ("8.1.33", CheckStatus.FAIL),
            ("8.2.29", CheckStatus.PASS),
            ("8.3.26", CheckStatus.FAIL),
            ("8.4.0RC1", CheckStatus.FAIL),
            ("8.4.14", CheckStatus.PASS),
            ("8.5.0", CheckStatus.PASS),
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_ci(php(ci_versions=[version]))), expected)

    def test_distribution_builds_report_their_upstream_version(self):
        # Ubuntu backports fixes into 8.1.2 without changing it, so this fails an 8.1.33 minimum.
        c = run_ci(php(ci_versions=["8.1.2-1ubuntu2.19"]), "8.1.33")
        self.assertEqual(failures(c)[1:], ["PHP 8.1.2-1ubuntu2.19 is below minimum 8.1.33 (command 'php artisan task0')"])
        self.assertEqual(outcome(run_ci(php(ci_versions=["8.1.2-1ubuntu2.19"]), "8.1")), CheckStatus.PASS)

    def test_unrecorded_version_fails(self):
        c = run_ci({"cicd": {"cmds": [{"cmd": "php a.php", "version": ""}]}})
        self.assertEqual(failures(c), [SUMMARY, "No PHP version recorded (command 'php a.php')"])

    def test_list_from_policy_input(self):
        saved = os.environ.pop("LUNAR_VAR_min_version_cicd", None)
        os.environ["LUNAR_VAR_min_version_cicd"] = "8.2.29\n8.3.27\n8.4.14"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                c = check_min_version_cicd(node=node_for(php(ci_versions=["8.4.1"])))
        finally:
            os.environ.pop("LUNAR_VAR_min_version_cicd")
            if saved is not None:
                os.environ["LUNAR_VAR_min_version_cicd"] = saved
        self.assertIn("PHP 8.4.1 is below minimum 8.4.14 (command 'php artisan task0')", failures(c))

    def test_invalid_minimum_fails(self):
        self.assertEqual(
            failures(run_ci(php(ci_versions=["8.4.14"]), "8.4.13, 8.4.14")),
            ["min_version_cicd lists PHP 8.4 twice: 8.4.13 and 8.4.14"],
        )


class SingleMinimumTest(unittest.TestCase):
    def test_same_ci_results_as_before_for_plain_versions(self):
        versions = ["7.4.33", "8.0.30", "8.1.0", "8.1.31", "8.2.27", "8.3.14", "8.4.1"]
        for minimum in ["8.1", "8.2", "8.1.31", "8.3.14", "8"]:
            for version in versions:
                with self.subTest(minimum=minimum, version=version):
                    expected = CheckStatus.PASS if truncated_comparison(version, minimum) else CheckStatus.FAIL
                    self.assertEqual(outcome(run_ci(php(ci_versions=[version]), minimum)), expected)


if __name__ == "__main__":
    unittest.main()
