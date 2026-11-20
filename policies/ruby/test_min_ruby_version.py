"""Unit tests for min-ruby-version and min-ruby-version-cicd.

Both take one minimum or one per release line ("3.3.10, 3.4.7, 4.0.1"), so a
vulnerable 3.4.1 can't pass just because it is newer than 3.3.10.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_ruby_version import check_min_ruby_version
from min_ruby_version_cicd import check_min_ruby_version_cicd

PER_LINE = "3.3.10, 3.4.7, 4.0.1"
SUMMARY = "CI ran Ruby that does not meet the minimum for its release line (3.3.10, 3.4.7, 4.0.1)"


def node_for(ruby, finished=True):
    data = {"lang": {"ruby": ruby}} if ruby is not None else {}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def ruby(version=None, ci_versions=None):
    data = {}
    if version is not None:
        data.update({"project_exists": True, "version": version})
    if ci_versions is not None:
        data["cicd"] = {"cmds": [{"cmd": f"ruby script{i}.rb", "version": v} for i, v in enumerate(ci_versions)]}
    return data


def run_build(data, minimum=PER_LINE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_ruby_version(minimum, node=node_for(data, finished))


def run_ci(data, minimum=PER_LINE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_ruby_version_cicd(minimum, node=node_for(data, finished))


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def padded_comparison(version, minimum):
    """The comparison both checks made before one minimum per release line."""
    actual, floor = (tuple(int(p) for p in str(x).split(".")) for x in (version, minimum))
    width = max(len(actual), len(floor))
    return actual + (0,) * (width - len(actual)) >= floor + (0,) * (width - len(floor))


class PerLineCicdTest(unittest.TestCase):
    def test_vulnerable_newer_line_fails(self):
        data = ruby(ci_versions=["3.4.1", "4.0.0"])
        self.assertEqual(outcome(run_ci(data, "3.3.10")), CheckStatus.PASS)
        self.assertEqual(
            failures(run_ci(data)),
            [
                SUMMARY,
                "Ruby 3.4.1 is below minimum 3.4.7 (command 'ruby script0.rb')",
                "Ruby 4.0.0 is below minimum 4.0.1 (command 'ruby script1.rb')",
            ],
        )

    def test_versions_against_a_list(self):
        for version, expected in [
            ("3.2.9", CheckStatus.FAIL),  # older than every listed line
            ("3.3.9", CheckStatus.FAIL),
            ("3.3.10", CheckStatus.PASS),
            ("3.4.7", CheckStatus.PASS),
            ("3.5.0", CheckStatus.FAIL),  # between 3.4 and 4.0
            ("4.0.1", CheckStatus.PASS),
            ("4.1.0", CheckStatus.PASS),  # newer than every listed line
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_ci(ruby(ci_versions=[version]))), expected)

    def test_unrecorded_version_is_skipped_as_before(self):
        c = run_ci({"cicd": {"cmds": [{"cmd": "ruby a.rb", "version": ""}, {"cmd": "ruby b.rb", "version": "3.4.7"}]}})
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))

    def test_list_from_policy_input(self):
        saved = os.environ.pop("LUNAR_VAR_min_ruby_version_cicd", None)
        os.environ["LUNAR_VAR_min_ruby_version_cicd"] = "3.3.10,3.4.7,4.0.1"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                c = check_min_ruby_version_cicd(node=node_for(ruby(ci_versions=["3.4.1"])))
        finally:
            os.environ.pop("LUNAR_VAR_min_ruby_version_cicd")
            if saved is not None:
                os.environ["LUNAR_VAR_min_ruby_version_cicd"] = saved
        self.assertIn("Ruby 3.4.1 is below minimum 3.4.7 (command 'ruby script0.rb')", failures(c))


class PerLineBuildTest(unittest.TestCase):
    def test_versions_against_a_list(self):
        for version, expected in [
            ("3.3.10", CheckStatus.PASS),
            ("3.3", CheckStatus.FAIL),  # names no patch release, so it counts as 3.3.0
            ("3.4.0preview2", CheckStatus.FAIL),
            ("4.0.1", CheckStatus.PASS),
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_build(ruby(version=version))), expected)

    def test_failure_messages(self):
        self.assertEqual(
            failures(run_build(ruby(version="3.3"))),
            ["Ruby version 3.3 is below minimum 3.3.10. Update to Ruby 3.3.10 or higher."],
        )
        self.assertEqual(
            failures(run_build(ruby(version="3.5.0"))),
            ["Ruby version 3.5.0 is on release line 3.5, which has no listed minimum (3.3.10, 3.4.7, 4.0.1)."],
        )

    def test_other_ruby_engines_are_not_recognized(self):
        # .ruby-version names JRuby and TruffleRuby by their own version numbers.
        for version in ["jruby-9.4.8.0", "truffleruby-24.1.1"]:
            with self.subTest(version=version):
                self.assertIn("is not a recognized version format", failures(run_build(ruby(version=version)))[0])

    def test_no_version_skips(self):
        self.assertEqual(outcome(run_build(ruby(version=""))), CheckStatus.SKIPPED)


class SingleMinimumTest(unittest.TestCase):
    def test_same_results_as_before_for_plain_versions(self):
        versions = ["2.7.8", "3.0", "3.0.0", "3.1.6", "3.2.5", "3.3", "3.3.5", "3.3.6", "3.4.1", "4.0.0"]
        for minimum in ["3.0", "3.1", "3.3.6", "2.7.8", "3"]:
            for version in versions:
                with self.subTest(minimum=minimum, version=version):
                    expected = CheckStatus.PASS if padded_comparison(version, minimum) else CheckStatus.FAIL
                    self.assertEqual(outcome(run_build(ruby(version=version), minimum)), expected)
                    self.assertEqual(outcome(run_ci(ruby(ci_versions=[version]), minimum)), expected)


if __name__ == "__main__":
    unittest.main()
