"""Unit tests for sonarqube.quality-gate-passing, on quality gates the sonarqube
collector's api and github-app sub-collectors write.

Run from this directory:
    python3 -m unittest test_quality_gate_passing -v
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import CheckStatus, Node  # noqa: E402

import quality_gate_passing  # noqa: E402

CLOUD_FAILED = {
    "status": "ERROR",
    "conditions_failed": 2,
    "failed_conditions": [
        {"text": "57.1% Coverage on New Code (required ≥ 80%)", "metric": "Coverage on New Code",
         "value": "57.1%", "required": "≥ 80%", "project_key": "acme_widgets"},
        {"text": "C Reliability Rating on New Code (required ≥ A)", "metric": "Reliability Rating on New Code",
         "value": "C", "required": "≥ A", "project_key": "acme_widgets"},
    ],
}
CHECK_RUN = {"name": "SonarCloud Code Analysis", "project_key": "acme_widgets", "conclusion": "failure",
             "title": "Quality Gate failed", "url": "https://sonarcloud.io/dashboard?id=acme_widgets&pullRequest=42",
             "quality_gate": "failed"}


def node(sonarqube=None, finished=True):
    data = {"lang": {"go": {"version": "1.22"}}}
    if sonarqube is not None:
        data["code_quality"] = {"native": {"sonarqube": sonarqube}}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def run(n):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return quality_gate_passing.main(node=n)


def status(c):
    """Check.status reports a skip as PASS, so read a skip from the results."""
    if any(r.result == CheckStatus.SKIPPED for r in c._results):
        return CheckStatus.SKIPPED
    return c.status


class QualityGatePassingTest(unittest.TestCase):
    def test_passing_gate(self):
        c = run(node({"quality_gate": {"status": "OK", "conditions_failed": 0}}))
        self.assertEqual(status(c), CheckStatus.PASS)

    def test_failed_gate_lists_each_failed_condition(self):
        c = run(node({"quality_gate": CLOUD_FAILED, "github_app": {"status": "complete", "check_runs": [CHECK_RUN]}}))
        self.assertEqual(status(c), CheckStatus.FAIL)
        self.assertEqual(c.failure_reasons, [
            "SonarQube quality gate is ERROR with 2 failed condition(s)",
            "57.1% Coverage on New Code (required ≥ 80%)",
            "C Reliability Rating on New Code (required ≥ A)",
        ])

    def test_failed_gate_without_conditions_keeps_the_headline(self):
        # The api sub-collector writes only the count.
        c = run(node({"quality_gate": {"status": "ERROR", "conditions_failed": 1}}))
        self.assertEqual(c.failure_reasons, ["SonarQube quality gate is ERROR with 1 failed condition(s)"])

    def test_unknown_condition_count(self):
        c = run(node({"quality_gate": {"status": "ERROR"}}))
        self.assertEqual(c.failure_reasons, ["SonarQube quality gate is ERROR with ? failed condition(s)"])

    def test_several_projects_name_the_project(self):
        gate = {"status": "ERROR", "conditions_failed": 2, "failed_conditions": [
            {"text": "2 New issues", "metric": "New issues", "value": "2", "project_key": "acme_api"},
            {"text": "45.0% Coverage on New Code (required ≥ 80%)", "metric": "Coverage on New Code",
             "value": "45.0%", "required": "≥ 80%", "project_key": "acme_web"},
        ]}
        c = run(node({"quality_gate": gate}))
        self.assertEqual(c.failure_reasons[1:], [
            "acme_api: 2 New issues",
            "acme_web: 45.0% Coverage on New Code (required ≥ 80%)",
        ])

    def test_failed_analysis_fails(self):
        run_ = {"name": "SonarCloud Code Analysis", "project_key": "acme_widgets", "conclusion": "cancelled",
                "title": "SonarQube Cloud analysis failed", "url": CHECK_RUN["url"]}
        c = run(node({"github_app": {"status": "complete", "check_runs": [run_]}}))
        self.assertEqual(status(c), CheckStatus.FAIL)
        self.assertEqual(c.failure_reasons,
                         ["SonarCloud Code Analysis reported no quality gate: SonarQube Cloud analysis failed"])

    def test_failed_analysis_next_to_a_passed_project_names_only_the_failed_one(self):
        failed = {"name": "[web] SonarQube Code Analysis", "project_key": "acme_web", "conclusion": "cancelled",
                  "title": None}
        passed = dict(CHECK_RUN, name="[api] SonarQube Code Analysis", conclusion="success",
                      title="Quality Gate passed", quality_gate="passed")
        c = run(node({"github_app": {"status": "complete", "check_runs": [passed, failed]}}))
        self.assertEqual(c.failure_reasons, ["[web] SonarQube Code Analysis reported no quality gate: cancelled"])

    def test_pending_check_run_skips(self):
        c = run(node({"github_app": {"status": "pending"}}))
        self.assertEqual(status(c), CheckStatus.SKIPPED)

    def test_no_sonarqube_data_skips(self):
        self.assertEqual(status(run(node())), CheckStatus.SKIPPED)

    def test_no_data_yet_is_pending(self):
        self.assertEqual(run(node(finished=False)).status, CheckStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
