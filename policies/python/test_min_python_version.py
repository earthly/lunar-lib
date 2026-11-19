"""Unit tests for min-python-version and min-python-version-cicd.

Both take one minimum or one per release line ("3.11.14, 3.12.12, 3.13.9"),
so a vulnerable 3.13.0 can't pass just because it is newer than 3.11.14.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_python_version import check_min_python_version
from min_python_version_cicd import check_min_python_version_cicd

PER_LINE = "3.11.14, 3.12.12, 3.13.9"
SUMMARY = "CI ran Python that does not meet the minimum for its release line (3.11.14, 3.12.12, 3.13.9)"


def node_for(python, finished=True):
    data = {"lang": {"python": python}} if python is not None else {}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def python(version=None, ci_versions=None):
    data = {}
    if version is not None:
        data.update({"project_exists": True, "version": version})
    if ci_versions is not None:
        data["cicd"] = {"cmds": [{"cmd": f"python app{i}.py", "version": v} for i, v in enumerate(ci_versions)]}
    return data


def run_build(data, minimum=PER_LINE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_python_version(minimum, node=node_for(data, finished))


def run_ci(data, minimum=PER_LINE, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_python_version_cicd(minimum, node=node_for(data, finished))


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
        # A single minimum passes 3.12.3 and 3.13.0 because they are newer than 3.11.14.
        data = python(ci_versions=["3.12.3", "3.13.0"])
        self.assertEqual(outcome(run_ci(data, "3.11.14")), CheckStatus.PASS)
        self.assertEqual(
            failures(run_ci(data)),
            [
                SUMMARY,
                "Python 3.12.3 is below minimum 3.12.12 (command 'python app0.py')",
                "Python 3.13.0 is below minimum 3.13.9 (command 'python app1.py')",
            ],
        )

    def test_each_line_meets_its_own_minimum(self):
        c = run_ci(python(ci_versions=["3.11.14", "3.12.12", "3.12.13", "3.13.9", "3.13.10"]))
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))

    def test_line_between_listed_ones_fails(self):
        c = run_ci(python(ci_versions=["3.12.12"]), "3.11.14, 3.13.9")
        self.assertEqual(
            failures(c)[1:],
            ["Python 3.12.12 is on release line 3.12, which has no listed minimum (command 'python app0.py')"],
        )

    def test_line_older_than_every_listed_one_fails(self):
        c = run_ci(python(ci_versions=["3.10.19"]))
        self.assertEqual(failures(c)[1:], ["Python 3.10.19 is below minimum 3.11.14 (command 'python app0.py')"])

    def test_line_newer_than_every_listed_one_passes(self):
        self.assertEqual(outcome(run_ci(python(ci_versions=["3.14.0", "3.15.0a1"]))), CheckStatus.PASS)

    def test_pre_releases_and_local_builds(self):
        for version, expected in [
            ("3.13.0rc1", CheckStatus.FAIL),  # below its line's minimum, like 3.13.0
            ("3.13.10rc1", CheckStatus.PASS),
            ("3.12.12+", CheckStatus.PASS),  # a local build of 3.12.12
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_ci(python(ci_versions=[version]))), expected)

    def test_unrecorded_or_unrecognized_version_fails(self):
        for entry, problem in [
            ({"cmd": "python a.py", "version": ""}, "No Python version recorded (command 'python a.py')"),
            (
                {"cmd": "python a.py", "version": "3.12 (PyPy)"},
                'Python version "3.12 (PyPy)" is not a recognized version format; expected a form like 3.12, '
                "3.12.8 or 3.13.0rc1 (command 'python a.py')",
            ),
        ]:
            with self.subTest(entry=entry):
                c = run_ci({"cicd": {"cmds": [entry, {"cmd": "python b.py", "version": "3.13.9"}]}})
                self.assertEqual(failures(c), [SUMMARY, problem])

    def test_no_commands_skips_and_pends_while_collecting(self):
        self.assertEqual(outcome(run_ci(python(version="3.13.9"))), CheckStatus.SKIPPED)
        self.assertEqual(outcome(run_ci(None, finished=False)), CheckStatus.PENDING)

    def test_list_from_policy_input(self):
        saved = os.environ.pop("LUNAR_VAR_min_python_version_cicd", None)
        os.environ["LUNAR_VAR_min_python_version_cicd"] = "[3.11.14, 3.12.12, 3.13.9]"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                c = check_min_python_version_cicd(node=node_for(python(ci_versions=["3.13.0"])))
        finally:
            os.environ.pop("LUNAR_VAR_min_python_version_cicd")
            if saved is not None:
                os.environ["LUNAR_VAR_min_python_version_cicd"] = saved
        self.assertIn("Python 3.13.0 is below minimum 3.13.9 (command 'python app0.py')", failures(c))

    def test_invalid_minimum_fails(self):
        data = python(ci_versions=["3.13.9"])
        self.assertEqual(
            failures(run_ci(data, "3.12.12, 3.12.13")),
            ["min_python_version_cicd lists Python 3.12 twice: 3.12.12 and 3.12.13"],
        )


class PerLineBuildTest(unittest.TestCase):
    def test_versions_against_a_list(self):
        for version, expected in [
            ("3.10.19", CheckStatus.FAIL),
            ("3.11.14", CheckStatus.PASS),
            ("3.12.11", CheckStatus.FAIL),
            ("3.13.9", CheckStatus.PASS),
            ("3.14.7", CheckStatus.PASS),
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_build(python(version=version))), expected)

    def test_failure_messages(self):
        self.assertEqual(
            failures(run_build(python(version="3.12.11"))),
            ["Python version 3.12.11 is below minimum 3.12.12. Update to Python 3.12.12 or higher."],
        )
        self.assertEqual(
            failures(run_build(python(version="3.12.11"), "3.11.14, 3.13.9")),
            ["Python version 3.12.11 is on release line 3.12, which has no listed minimum (3.11.14, 3.13.9)."],
        )
        self.assertIn(
            'min_python_version entry "latest" is not a recognized version format',
            failures(run_build(python(version="3.13.9"), "3.12.12, latest"))[0],
        )


class SingleMinimumTest(unittest.TestCase):
    def test_same_results_as_before_for_plain_versions(self):
        versions = ["2.7.18", "3.8.10", "3.9", "3.9.0", "3.9.21", "3.10.19", "3.11.9", "3.12", "3.12.7", "3.12.12", "3.13.9", "3.14.7"]
        for minimum in ["3.9", "3.10", "3.12", "3.12.12", "3.9.0", "3"]:
            for version in versions:
                with self.subTest(minimum=minimum, version=version):
                    expected = CheckStatus.PASS if padded_comparison(version, minimum) else CheckStatus.FAIL
                    self.assertEqual(outcome(run_build(python(version=version), minimum)), expected)
                    self.assertEqual(outcome(run_ci(python(ci_versions=[version]), minimum)), expected)


if __name__ == "__main__":
    unittest.main()
