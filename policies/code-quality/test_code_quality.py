"""Unit tests for the code-quality checks' rerun hint: a check that fails because
the scanner hadn't reported on a pull request's commit yet ends with the
`/lunar rerun` comment that re-checks it."""

import importlib.util
import io
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from lunar_policy import CheckStatus, Node

POLICY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(POLICY_DIR))


def load_policy(filename):
    spec = importlib.util.spec_from_file_location(filename, POLICY_DIR / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


executed = load_policy("executed")
passing = load_policy("passing")
min_coverage = load_policy("min_coverage")
max_duplication = load_policy("max_duplication")
max_severity = load_policy("max_severity")
max_total = load_policy("max_total")

# What each check reports when the scanner's results aren't there.
NOT_AVAILABLE = (
    (passing, "Code-quality pass/fail signal not available. "
              "Ensure collector reports .code_quality.passing."),
    (min_coverage, "Line coverage not reported. "
                   "Ensure the scanner publishes .code_quality.coverage_percentage."),
    (max_duplication, "Duplication percentage not reported. "
                      "Ensure the scanner publishes .code_quality.duplication_percentage."),
    (max_severity, "Issue counts not available. Ensure the scanner publishes .code_quality.issues."),
    (max_total, "Total issue count not available. "
                "Ensure the scanner publishes .code_quality.issues.total."),
)
HINT = ("The scanner hadn't reported on this commit when Lunar checked. Once it has, "
        "comment `/lunar rerun {}` to re-check without a new commit.")


def pending(integration="github_app", tool="sonarqube"):
    """What the sonarqube collector writes when the analysis isn't in yet."""
    source = {"integration": integration, "analysis_status": "pending"}
    if tool:
        source["tool"] = tool
    return {"lang": {"python": {}},
            "code_quality": {"source": source,
                             "native": {"sonarqube": {"github_app": {"status": "pending"}}}}}


def evaluate(check, data, pr="8", **env):
    values = {f"LUNAR_VAR_{k}": v for k, v in env.items()}
    values.setdefault("LUNAR_VAR_max_total_threshold", "50")
    values["LUNAR_COMPONENT_PR"] = pr
    node = Node.from_component_json(data, bundle_info={"workflows_finished": True})
    with mock.patch.dict(os.environ, values):
        return check(node)


def messages(check):
    return [r.failure_message for r in check._results if r.failure_message]


class TestRerunHint(unittest.TestCase):

    def test_pending_analysis_ends_with_the_comment(self):
        for integration in ("github_app", "api", "auto"):
            for check, message in NOT_AVAILABLE:
                with self.subTest(check=check.__module__, integration=integration):
                    result = evaluate(check, pending(integration))
                    self.assertEqual(result.status, CheckStatus.FAIL)
                    self.assertEqual(messages(result), [message + " " + HINT.format("sonarqube")])

    def test_no_hint_off_a_pull_request(self):
        for pr in ("", "0"):
            for check, message in NOT_AVAILABLE:
                with self.subTest(check=check.__module__, pr=pr):
                    self.assertEqual(messages(evaluate(check, pending(), pr=pr)), [message])

    def test_no_hint_when_the_analysis_is_not_pending(self):
        # A scanner that finished without a number is not fixed by a rerun.
        data = pending()
        data["code_quality"]["source"]["analysis_status"] = "complete"
        del data["code_quality"]["native"]
        for check, message in NOT_AVAILABLE:
            with self.subTest(check=check.__module__):
                self.assertEqual(messages(evaluate(check, data)), [message])

    def test_renamed_collector_import(self):
        # A sonarqube collector imported with `name: sonar-cloud` registers
        # `sonar-cloud.*`; the input is used as written.
        result = evaluate(passing, pending(), rerun_collectors="sonar-cloud")
        self.assertEqual(messages(result), [NOT_AVAILABLE[0][1] + " " + HINT.format("sonar-cloud")])
        # No message names a policy; the report's check header carries that.
        self.assertNotIn("code-quality.", messages(result)[0])

    def test_empty_turns_it_off(self):
        self.assertEqual(messages(evaluate(passing, pending(), rerun_collectors="")),
                         [NOT_AVAILABLE[0][1]])

    def test_no_hint_without_the_tool(self):
        self.assertEqual(messages(evaluate(passing, pending(tool=None))), [NOT_AVAILABLE[0][1]])

    def test_malformed_name_drops_the_hint_without_changing_the_verdict(self):
        with redirect_stderr(io.StringIO()) as log:
            result = evaluate(passing, pending(), rerun_collectors="sonar`qube")
        self.assertIn("rerun_collectors: no rerun hint", log.getvalue())
        self.assertEqual(result.status, CheckStatus.FAIL)
        self.assertEqual(messages(result), [NOT_AVAILABLE[0][1]])

    def test_executed_still_passes_on_a_pending_analysis(self):
        self.assertEqual(evaluate(executed, pending()).status, CheckStatus.PASS)

    def test_finished_results_are_unchanged(self):
        data = {"lang": {"python": {}}, "code_quality": {
            "source": {"tool": "sonarqube", "integration": "api", "analysis_status": "complete"},
            "passing": True, "coverage_percentage": 91.5, "duplication_percentage": 1.2,
            "issues": {"total": 3, "critical": 0, "high": 0, "medium": 1, "low": 2}}}
        for check in (passing, min_coverage, max_duplication, max_severity, max_total):
            with self.subTest(check=check.__module__):
                self.assertEqual(evaluate(check, data).status, CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()
