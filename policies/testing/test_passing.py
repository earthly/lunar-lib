"""Unit tests for the testing policy's `passing` check."""

import unittest

from lunar_policy import CheckStatus, Node

from passing import check_passing


def run(job, all_passing, attempt=1, run_id="100", step=4, pipeline="CI", failed=None, total=10):
    failed = (0 if all_passing else 1) if failed is None else failed
    return {
        "pipeline": pipeline, "run_id": run_id, "attempt": attempt, "job": job, "step": step,
        "total": total, "passed": total - failed, "failed": failed, "skipped": 0,
        "all_passing": all_passing,
    }


def check(testing, lang=True, finished=True):
    data = {"lang": {"java": {}}} if lang else {}
    if testing is not None:
        data["testing"] = testing
    return check_passing(Node.from_component_json(data, bundle_info={"workflows_finished": finished}))


class TestPassing(unittest.TestCase):
    def test_failing_job_is_not_hidden_by_a_later_passing_one(self):
        # The integration job failed, then the unit job finished last and set
        # the scalar to true.
        c = check({
            "all_passing": True,
            "runs": [run("integration", False, step=3), run("unit", True, step=3)],
        })
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertIn("CI / integration (1 of 10 failed)", c.failure_reasons[0])

    def test_failing_matrix_leg_fails(self):
        # Matrix legs share run, job and step; one red leg is enough.
        c = check({"runs": [run("build", True), run("build", False)]})
        self.assertEqual(c.status, CheckStatus.FAIL)

    def test_rerun_replaces_its_own_failed_attempt(self):
        c = check({"runs": [run("build", False, attempt=1), run("build", True, attempt=2)]})
        self.assertEqual(c.status, CheckStatus.PASS)

    def test_rerun_of_one_job_does_not_clear_another(self):
        c = check({"runs": [
            run("unit", False, attempt=1), run("integration", False, attempt=1),
            run("unit", True, attempt=2),
        ]})
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertIn("CI / integration", c.failure_reasons[0])
        self.assertNotIn("CI / unit", c.failure_reasons[0])

    def test_reruns_are_scoped_to_their_ci_run(self):
        # A newer attempt of another pipeline run doesn't replace this one.
        c = check({"runs": [run("build", False, run_id="100"), run("build", True, run_id="200", attempt=3)]})
        self.assertEqual(c.status, CheckStatus.FAIL)

    def test_all_runs_passing(self):
        c = check({"all_passing": True, "runs": [run("unit", True), run("integration", True, step=5)]})
        self.assertEqual(c.status, CheckStatus.PASS)

    def test_falls_back_to_all_passing_without_runs(self):
        self.assertEqual(check({"all_passing": True}).status, CheckStatus.PASS)
        c = check({"all_passing": False})
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertEqual(c.failure_reasons, ["Tests are failing. Check CI logs for test failure details."])

    def test_no_test_data_fails_after_collection(self):
        c = check({"source": {"tool": "maven-surefire", "integration": "ci"}})
        self.assertEqual(c.status, CheckStatus.FAIL)
        self.assertIn("Test pass/fail data not available", c.failure_reasons[0])

    def test_pending_while_collecting(self):
        self.assertEqual(check(None, finished=False).status, CheckStatus.PENDING)

    def test_skips_without_a_language_project(self):
        c = check(None, lang=False)
        self.assertEqual(c._results[0].result, CheckStatus.SKIPPED)


if __name__ == "__main__":
    unittest.main()
