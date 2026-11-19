"""Unit tests for min-go-version and min-go-version-cicd.

Both take one minimum or one per release line ("1.26.9, 1.27.4"), so a
vulnerable 1.27.3 can't pass just because it is newer than 1.26.9.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_go_version import check_min_go_version
from min_go_version_cicd import check_min_go_version_cicd

PER_LINE = "1.26.9, 1.27.4"
SUMMARY = "CI ran Go that does not meet the minimum for its release line (1.26.9, 1.27.4)"


def node_for(go, finished=True):
    data = {"lang": {"go": go}} if go is not None else {}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def golang(version=None, ci_versions=None):
    data = {}
    if version is not None:
        data.update({"project_exists": True, "version": version})
    if ci_versions is not None:
        data["cicd"] = {"cmds": [{"cmd": f"go test ./pkg{i}/...", "version": v} for i, v in enumerate(ci_versions)]}
    return data


def run_build(data, minimum=PER_LINE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_go_version(minimum, node=node_for(data, finished))


def run_ci(data, minimum=PER_LINE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_go_version_cicd(minimum, node=node_for(data, finished))


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def truncated_comparison(version, minimum):
    """The comparison both checks made before: the version cut to the minimum's length."""
    actual, floor = (tuple(int(p) for p in str(x).split(".")) for x in (version, minimum))
    return actual[: len(floor)] >= floor


class PerLineCicdTest(unittest.TestCase):
    def test_vulnerable_newer_line_fails(self):
        # A single minimum passes 1.27.3 because it is newer than 1.26.9.
        data = golang(ci_versions=["1.27.3"])
        self.assertEqual(outcome(run_ci(data, "1.26.9")), CheckStatus.PASS)
        self.assertEqual(
            failures(run_ci(data)),
            [SUMMARY, "Go 1.27.3 is below minimum 1.27.4 (command 'go test ./pkg0/...')"],
        )

    def test_versions_against_a_list(self):
        for version, expected in [
            ("1.25.14", CheckStatus.FAIL),  # older than every listed line
            ("1.26.8", CheckStatus.FAIL),
            ("1.26.9", CheckStatus.PASS),
            ("1.27.0", CheckStatus.FAIL),
            ("1.27.4", CheckStatus.PASS),
            ("1.28rc1", CheckStatus.PASS),  # newer than every listed line
            ("1.28.0", CheckStatus.PASS),
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_ci(golang(ci_versions=[version]))), expected)

    def test_line_between_listed_ones_fails(self):
        c = run_ci(golang(ci_versions=["1.26.9"]), "1.25.14, 1.27.4")
        self.assertEqual(
            failures(c)[1:],
            ["Go 1.26.9 is on release line 1.26, which has no listed minimum (command 'go test ./pkg0/...')"],
        )

    def test_pre_release_sorts_before_its_release(self):
        self.assertEqual(
            failures(run_ci(golang(ci_versions=["1.27rc2"])))[1:],
            ["Go 1.27rc2 is below minimum 1.27.4 (command 'go test ./pkg0/...')"],
        )

    def test_unrecorded_or_unrecognized_version_fails(self):
        for entry, problem in [
            ({"cmd": "go build", "version": ""}, "No Go version recorded (command 'go build')"),
            (
                {"cmd": "go build", "version": "devel"},
                'Go version "devel" is not a recognized version format; expected a form like 1.22, 1.22.7 '
                "or 1.23rc1 (command 'go build')",
            ),
        ]:
            with self.subTest(entry=entry):
                c = run_ci({"cicd": {"cmds": [entry, {"cmd": "go vet", "version": "1.27.4"}]}})
                self.assertEqual(failures(c), [SUMMARY, problem])

    def test_no_commands_skips_and_pends_while_collecting(self):
        self.assertEqual(outcome(run_ci(golang(version="1.27"))), CheckStatus.SKIPPED)
        self.assertEqual(outcome(run_ci(None, finished=False)), CheckStatus.PENDING)

    def test_list_from_policy_input(self):
        saved = os.environ.pop("LUNAR_VAR_min_go_version_cicd", None)
        os.environ["LUNAR_VAR_min_go_version_cicd"] = "1.26.9 1.27.4"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                c = check_min_go_version_cicd(node=node_for(golang(ci_versions=["1.27.3"])))
        finally:
            os.environ.pop("LUNAR_VAR_min_go_version_cicd")
            if saved is not None:
                os.environ["LUNAR_VAR_min_go_version_cicd"] = saved
        self.assertIn("Go 1.27.3 is below minimum 1.27.4 (command 'go test ./pkg0/...')", failures(c))


class PerLineGoModTest(unittest.TestCase):
    """go.mod's go line is the oldest Go the module builds with, so it is compared in full."""

    def test_go_lines_against_a_list(self):
        for version, expected in [
            ("1.22", CheckStatus.FAIL),
            ("1.26", CheckStatus.FAIL),  # the same as 1.26.0
            ("1.26.0", CheckStatus.FAIL),
            ("1.26.9", CheckStatus.PASS),
            ("1.27.4", CheckStatus.PASS),
            ("1.28", CheckStatus.PASS),
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_build(golang(version=version))), expected)

    def test_failure_messages(self):
        self.assertEqual(
            failures(run_build(golang(version="1.27"))),
            ["Go version 1.27 is below minimum 1.27.4. Update go.mod to require Go 1.27.4 or higher."],
        )
        self.assertEqual(
            failures(run_build(golang(version="1.26.9"), "1.25.14, 1.27.4")),
            ["Go version 1.26.9 is on release line 1.26, which has no listed minimum (1.25.14, 1.27.4)."],
        )


class SingleMinimumTest(unittest.TestCase):
    def test_same_results_as_before_for_plain_versions(self):
        versions = ["1.20", "1.21", "1.21.0", "1.21.13", "1.22", "1.22.5", "1.22.7", "1.23.0", "1.25.14"]
        for minimum in ["1.21", "1.22", "1.22.7", "1.23.4", "1"]:
            for version in versions:
                with self.subTest(minimum=minimum, version=version):
                    expected = CheckStatus.PASS if truncated_comparison(version, minimum) else CheckStatus.FAIL
                    self.assertEqual(outcome(run_build(golang(version=version), minimum)), expected)
                    self.assertEqual(outcome(run_ci(golang(ci_versions=[version]), minimum)), expected)

    def test_minimum_with_a_zero_patch_accepts_its_line(self):
        # Truncating made go 1.22 fail a 1.22.0 minimum; 1.22 is 1.22.0.
        self.assertFalse(truncated_comparison("1.22", "1.22.0"))
        self.assertEqual(outcome(run_build(golang(version="1.22"), "1.22.0")), CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()
