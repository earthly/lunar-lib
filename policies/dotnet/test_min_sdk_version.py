"""Unit tests for min-sdk-version and min-sdk-version-cicd.

Microsoft patches each SDK feature band separately, so a release line is
major.minor plus the band: 8.0.122 and 8.0.416 are on 8.0.1xx and 8.0.4xx.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_sdk_version import check_min_sdk_version
from min_sdk_version_cicd import check_min_sdk_version_cicd

PER_BAND = "8.0.122, 8.0.416, 10.0.101"
SUMMARY = "CI ran .NET SDK that does not meet the minimum for its release line (8.0.122, 8.0.416, 10.0.101)"


def node_for(dotnet, finished=True):
    data = {"lang": {"dotnet": dotnet}} if dotnet is not None else {}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def dotnet(sdk_version=None, ci_versions=None):
    data = {}
    if sdk_version is not None:
        data.update({"project_exists": True, "sdk_version": sdk_version})
    if ci_versions is not None:
        data["cicd"] = {"cmds": [{"cmd": f"dotnet build Proj{i}.csproj", "version": v} for i, v in enumerate(ci_versions)]}
    return data


def run_build(data, minimum=PER_BAND, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_sdk_version(minimum, node=node_for(data, finished))


def run_ci(data, minimum=PER_BAND, finished=True):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_sdk_version_cicd(minimum, node=node_for(data, finished))


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def three_part_comparison(version, minimum):
    """The comparison before: major.minor.patch, anything after the patch ignored."""
    import re

    def parse(v):
        m = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", str(v).strip())
        return (int(m[1]), int(m[2]), int(m[3] or 0)) if m else None

    actual, floor = parse(version), parse(minimum)
    return actual is not None and floor is not None and actual >= floor


class PerBandCicdTest(unittest.TestCase):
    def test_patched_sdk_in_every_band_passes(self):
        # The same security release ships as 8.0.122 and 8.0.416; a single 8.0.416 minimum fails 8.0.122.
        data = dotnet(ci_versions=["8.0.122", "8.0.416", "10.0.101"])
        self.assertEqual(outcome(run_ci(data)), CheckStatus.PASS)
        self.assertEqual(
            failures(run_ci(data, "8.0.416")),
            ["CI ran .NET SDK that does not meet minimum 8.0.416", ".NET SDK 8.0.122 is below minimum 8.0.416 (command 'dotnet build Proj0.csproj')"],
        )

    def test_versions_against_a_list(self):
        for version, expected in [
            ("6.0.428", CheckStatus.FAIL),  # older than every listed line
            ("8.0.121", CheckStatus.FAIL),
            ("8.0.122", CheckStatus.PASS),
            ("8.0.319", CheckStatus.FAIL),  # 8.0.3xx has no listed minimum
            ("8.0.415", CheckStatus.FAIL),
            ("8.0.416", CheckStatus.PASS),
            ("9.0.306", CheckStatus.FAIL),  # between 8.0 and 10.0
            ("10.0.100", CheckStatus.FAIL),
            ("10.0.101", CheckStatus.PASS),
            ("10.0.200", CheckStatus.PASS),  # newer than every listed line
            ("11.0.100-preview.1.26104.118", CheckStatus.PASS),
        ]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_ci(dotnet(ci_versions=[version]))), expected)

    def test_unlisted_band_message(self):
        self.assertEqual(
            failures(run_ci(dotnet(ci_versions=["8.0.319"])))[1:],
            [".NET SDK 8.0.319 is on release line 8.0.3xx, which has no listed minimum (command 'dotnet build Proj0.csproj')"],
        )

    def test_major_minor_entry_covers_every_band(self):
        # 8.0.x and 8.0 mean any 8.0 SDK; only 10.0 needs a patched band here.
        for version, expected in [("8.0.122", CheckStatus.PASS), ("8.0.319", CheckStatus.PASS), ("9.0.306", CheckStatus.FAIL), ("10.0.100", CheckStatus.FAIL)]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_ci(dotnet(ci_versions=[version]), "8.0.x, 10.0.101")), expected)

    def test_unrecorded_version_is_skipped_as_before(self):
        c = run_ci({"cicd": {"cmds": [{"cmd": "dotnet app.dll", "version": ""}, {"cmd": "dotnet test", "version": "8.0.416"}]}})
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))

    def test_list_from_policy_input(self):
        saved = os.environ.pop("LUNAR_VAR_min_sdk_version_cicd", None)
        os.environ["LUNAR_VAR_min_sdk_version_cicd"] = "8.0.122, 8.0.416, 10.0.101"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                c = check_min_sdk_version_cicd(node=node_for(dotnet(ci_versions=["8.0.415"])))
        finally:
            os.environ.pop("LUNAR_VAR_min_sdk_version_cicd")
            if saved is not None:
                os.environ["LUNAR_VAR_min_sdk_version_cicd"] = saved
        self.assertIn(".NET SDK 8.0.415 is below minimum 8.0.416 (command 'dotnet build Proj0.csproj')", failures(c))

    def test_overlapping_entries_fail(self):
        for minimum, error in [
            ("8.0.416, 8.0.410", "min_sdk_version_cicd lists .NET SDK 8.0.4xx twice: 8.0.416 and 8.0.410"),
            ("8.0, 8.0.416", "min_sdk_version_cicd lists .NET SDK 8.0 twice: 8.0 and 8.0.416"),
        ]:
            with self.subTest(minimum=minimum):
                self.assertEqual(failures(run_ci(dotnet(ci_versions=["8.0.416"]), minimum)), [error])


class PerBandGlobalJsonTest(unittest.TestCase):
    def test_versions_against_a_list(self):
        for version, expected in [("8.0.100", CheckStatus.FAIL), ("8.0.122", CheckStatus.PASS), ("8.0.400", CheckStatus.FAIL), ("10.0.101", CheckStatus.PASS)]:
            with self.subTest(version=version):
                self.assertEqual(outcome(run_build(dotnet(sdk_version=version))), expected)

    def test_failure_message(self):
        self.assertEqual(
            failures(run_build(dotnet(sdk_version="8.0.400"))),
            [".NET SDK version 8.0.400 is below minimum 8.0.416. Update global.json to specify SDK version 8.0.416 or higher."],
        )


class SingleMinimumTest(unittest.TestCase):
    def test_same_results_as_before_for_release_versions(self):
        versions = ["6.0.428", "7.0.410", "8.0", "8.0.100", "8.0.122", "8.0.416", "9.0.100", "10.0.101"]
        for minimum in ["8.0", "8.0.100", "8.0.416", "9.0", "8.0.x"]:
            for version in versions:
                with self.subTest(minimum=minimum, version=version):
                    expected = CheckStatus.PASS if three_part_comparison(version, minimum) else CheckStatus.FAIL
                    self.assertEqual(outcome(run_build(dotnet(sdk_version=version), minimum)), expected)
                    self.assertEqual(outcome(run_ci(dotnet(ci_versions=[version]), minimum)), expected)

    def test_changed_results(self):
        # A major-only minimum didn't parse and failed every SDK; a preview passed its release's minimum.
        self.assertFalse(three_part_comparison("8.0.416", "8"))
        self.assertEqual(outcome(run_ci(dotnet(ci_versions=["8.0.416"]), "8")), CheckStatus.PASS)
        self.assertTrue(three_part_comparison("10.0.100-rc.2.25502.107", "10.0.100"))
        self.assertEqual(outcome(run_ci(dotnet(ci_versions=["10.0.100-rc.2.25502.107"]), "10.0.100")), CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
