"""Unit tests for min-node-version and min-node-version-cicd.

Both checks compare full versions and take one minimum or one per major
release ("20.19.5, 22.20.0, 24.10.0"). They used to compare only the major, so
a patch-level minimum such as 20.15.1 passed 20.0.0.
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "checks"))

from lunar_policy import CheckStatus, Node  # noqa: E402

from min_node_version import check_min_node_version  # noqa: E402
from min_node_version_cicd import check_min_node_version_cicd  # noqa: E402

PER_MAJOR = "20.19.5, 22.20.0, 24.10.0"
SUMMARY = "CI ran Node.js that does not meet the minimum for its release line (20.19.5, 22.20.0, 24.10.0)"


def node_for(nodejs, finished=True):
    data = {"lang": {"nodejs": nodejs}} if nodejs is not None else {}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def nodejs(version=None, ci_versions=None):
    data = {}
    if version is not None:
        data.update({"project_exists": True, "package_json_exists": True, "version": version})
    if ci_versions is not None:
        data["cicd"] = {"cmds": [{"cmd": f"node app-{i}.js", "version": v} for i, v in enumerate(ci_versions)]}
    return data


def run_build(data, minimum=PER_MAJOR, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_node_version(minimum, node=node_for(data, finished))


def run_ci(data, minimum=PER_MAJOR, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_node_version_cicd(minimum, node=node_for(data, finished))


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def majors_only(version, minimum):
    """The comparison both checks made before they compared full versions."""
    return int(str(version).strip().lstrip("vV").split(".")[0]) >= int(str(minimum).strip().lstrip("vV").split(".")[0])


class FullVersionComparisonTest(unittest.TestCase):
    """Regression tests for the change from comparing majors to comparing full versions."""

    def test_patch_level_minimum_now_fails_versions_that_passed(self):
        for minimum, version in [
            ("20.15.1", "20.0.0"),
            ("20.15.1", "20.15.0"),
            ("18.20.4", "18.19.1"),
            ("22.4.1", "22.3.0"),
        ]:
            with self.subTest(minimum=minimum, version=version):
                self.assertTrue(majors_only(version, minimum), "passed when only the major was compared")
                build = run_build(nodejs(version=version), minimum)
                self.assertEqual(
                    failures(build),
                    [f"Node.js version {version} is below minimum {minimum}. Update to Node.js {minimum} or higher."],
                )
                ci = run_ci(nodejs(ci_versions=[version]), minimum)
                self.assertEqual(
                    failures(ci),
                    [
                        f"CI ran Node.js that does not meet minimum {minimum}",
                        f"Node.js {version} is below minimum {minimum} (command 'node app-0.js')",
                    ],
                )

    def test_patch_level_minimum_still_passes_its_patch_and_newer(self):
        for version in ["20.15.1", "20.15.2", "20.19.5", "22.0.0"]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_build(nodejs(version=version), "20.15.1")), CheckStatus.PASS)
                self.assertEqual(outcome(run_ci(nodejs(ci_versions=[version]), "20.15.1")), CheckStatus.PASS)

    def test_major_only_minimum_gives_the_same_results(self):
        versions = ["16.20.2", "18.0.0", "18.20.8", "v18.20.8", "20.0.0", "20.19.5", "21.7.3", "22.0.0", "24.10.0", "25.1.0"]
        for minimum in ["16", "18", "20", "v20", "20.x", " 22 "]:
            for version in versions:
                with self.subTest(minimum=minimum, version=version):
                    expected = CheckStatus.PASS if majors_only(version, minimum) else CheckStatus.FAIL
                    self.assertEqual(outcome(run_build(nodejs(version=version), minimum)), expected)
                    self.assertEqual(outcome(run_ci(nodejs(ci_versions=[version]), minimum)), expected)

    def test_pre_release_sorts_before_its_release(self):
        # 22.0.0-rc.1 passed a 22 minimum when only the major was compared.
        c = run_ci(nodejs(ci_versions=["22.0.0-rc.1"]), "22")
        self.assertEqual(failures(c)[1:], ["Node.js 22.0.0-rc.1 is below minimum 22 (command 'node app-0.js')"])
        self.assertEqual(outcome(run_ci(nodejs(ci_versions=["22.0.0-rc.1"]), "20")), CheckStatus.PASS)


class PerMajorCicdTest(unittest.TestCase):
    def test_vulnerable_newer_major_fails(self):
        # A single minimum passes 22.12.0 because it is newer than 20.19.5.
        data = nodejs(ci_versions=["22.12.0", "24.9.0"])
        self.assertEqual(outcome(run_ci(data, "20.19.5")), CheckStatus.PASS)
        self.assertEqual(
            failures(run_ci(data)),
            [
                SUMMARY,
                "Node.js 22.12.0 is below minimum 22.20.0 (command 'node app-0.js')",
                "Node.js 24.9.0 is below minimum 24.10.0 (command 'node app-1.js')",
            ],
        )

    def test_each_major_meets_its_own_minimum(self):
        c = run_ci(nodejs(ci_versions=["20.19.5", "20.20.0", "22.20.0", "22.21.1", "24.10.0", "24.11.0"]))
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))

    def test_major_between_listed_ones_fails(self):
        for version in ["21.7.3", "23.11.1"]:
            with self.subTest(version=version):
                major = version.split(".")[0]
                self.assertEqual(
                    failures(run_ci(nodejs(ci_versions=[version]))),
                    [SUMMARY, f"Node.js {version} is on release line {major}, which has no listed minimum (command 'node app-0.js')"],
                )

    def test_major_older_than_every_listed_one_fails(self):
        c = run_ci(nodejs(ci_versions=["18.20.8"]))
        self.assertEqual(failures(c)[1:], ["Node.js 18.20.8 is below minimum 20.19.5 (command 'node app-0.js')"])

    def test_major_newer_than_every_listed_one_passes(self):
        self.assertEqual(outcome(run_ci(nodejs(ci_versions=["25.0.0", "26.1.0"]))), CheckStatus.PASS)

    def test_same_problem_is_reported_once(self):
        c = run_ci(nodejs(ci_versions=["22.12.0", "20.19.5", "22.12.0", "23.1.0"]))
        self.assertEqual(
            failures(c),
            [
                SUMMARY,
                "Node.js 22.12.0 is below minimum 22.20.0 (2 commands, e.g. 'node app-0.js')",
                "Node.js 23.1.0 is on release line 23, which has no listed minimum (command 'node app-3.js')",
            ],
        )

    def test_unrecorded_or_unrecognized_version_fails(self):
        for entry, problem in [
            ({"cmd": "node a.js", "version": ""}, "No Node.js version recorded (command 'node a.js')"),
            ({"cmd": "node a.js"}, "No Node.js version recorded (command 'node a.js')"),
            (
                {"cmd": "node a.js", "version": "latest"},
                'Node.js version "latest" is not a recognized version format; expected a form like 20, 20.15.1 '
                "or v20.15.1 (command 'node a.js')",
            ),
        ]:
            with self.subTest(entry=entry):
                c = run_ci({"cicd": {"cmds": [entry, {"cmd": "node b.js", "version": "22.20.0"}]}})
                self.assertEqual(failures(c), [SUMMARY, problem])

    def test_no_commands_skips_and_pends_while_collecting(self):
        self.assertEqual(outcome(run_ci(nodejs(version="22.20.0"))), CheckStatus.SKIPPED)
        self.assertEqual(outcome(run_ci(None, finished=False)), CheckStatus.PENDING)

    def test_list_from_policy_input(self):
        saved = os.environ.get("LUNAR_VAR_min_node_version_cicd")
        os.environ["LUNAR_VAR_min_node_version_cicd"] = "20.19.5\n22.20.0  # LTS\n24.10.0"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                c = check_min_node_version_cicd(node=node_for(nodejs(ci_versions=["22.12.0"])))
        finally:
            os.environ.pop("LUNAR_VAR_min_node_version_cicd")
            if saved is not None:
                os.environ["LUNAR_VAR_min_node_version_cicd"] = saved
        self.assertIn("Node.js 22.12.0 is below minimum 22.20.0 (command 'node app-0.js')", failures(c))

    def test_invalid_minimum_fails(self):
        data = nodejs(ci_versions=["22.20.0"])
        self.assertEqual(
            failures(run_ci(data, "20.19.5, 20.20.0")),
            ["min_node_version_cicd lists Node.js 20 twice: 20.19.5 and 20.20.0"],
        )
        self.assertIn('min_node_version_cicd entry ">=22"', failures(run_ci(data, "20.19.5, >=22"))[0])


class PerMajorBuildTest(unittest.TestCase):
    def test_versions_against_a_list(self):
        for version, expected in [
            ("20.19.5", CheckStatus.PASS),
            ("20.18.0", CheckStatus.FAIL),
            ("21.7.3", CheckStatus.FAIL),
            ("22.23.4", CheckStatus.PASS),
            ("24.9.0", CheckStatus.FAIL),
            ("25.0.0", CheckStatus.PASS),
            ("18.20.8", CheckStatus.FAIL),
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_build(nodejs(version=version))), expected)

    def test_failure_messages(self):
        self.assertEqual(
            failures(run_build(nodejs(version="21.7.3"))),
            ["Node.js version 21.7.3 is on release line 21, which has no listed minimum (20.19.5, 22.20.0, 24.10.0)."],
        )
        self.assertEqual(
            failures(run_build(nodejs(version="22.12.0"))),
            ["Node.js version 22.12.0 is below minimum 22.20.0. Update to Node.js 22.20.0 or higher."],
        )

    def test_invalid_minimum_fails_instead_of_erroring(self):
        c = run_build(nodejs(version="22.20.0"), ">=20")
        self.assertEqual(outcome(c), CheckStatus.FAIL)
        self.assertIn('min_node_version ">=20" is not a recognized version format', failures(c)[0])


if __name__ == "__main__":
    unittest.main()
