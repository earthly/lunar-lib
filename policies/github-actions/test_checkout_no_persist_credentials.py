"""Unit tests for checkout-no-persist-credentials and its `exempt_jobs` input."""

import importlib.util
import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

from lunar_policy import CheckStatus, Node


def load_policy(filename):
    policy_dir = Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_"), policy_dir / f"{filename}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


check_persist_credentials = load_policy("checkout_no_persist_credentials")
check_permissions_declared = load_policy("permissions_declared")


@contextmanager
def policy_vars(**kwargs):
    saved = {}
    try:
        for key, value in kwargs.items():
            env_key = f"LUNAR_VAR_{key}"
            saved[env_key] = os.environ.get(env_key)
            os.environ[env_key] = value
        yield
    finally:
        for env_key, old in saved.items():
            if old is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = old


def is_skipped(check):
    """check.status never returns SKIPPED; a skip is recorded as a SKIPPED result."""
    return any(r.result == CheckStatus.SKIPPED for r in check._results)


def checkout(name="Checkout", persist=None):
    step = {"name": name, "uses": "actions/checkout@v4"}
    if persist is not None:
        step["with"] = {"persist-credentials": persist}
    return step


def node(workflows):
    return Node.from_component_json(
        {"ci": {"native": {"github_actions": {"workflows": workflows}}}},
        {"workflows_finished": True},
    )


PUBLISH = {
    "file": ".github/workflows/publish.yaml",
    "jobs": {"push": {"steps": [checkout("Checkout repo")]}},
}
DEPLOY = {
    "file": ".github/workflows/deploy.yaml",
    "jobs": {"push": {"steps": [checkout()]}},
}
CI = {
    "file": ".github/workflows/ci.yaml",
    "jobs": {"build": {"steps": [checkout()]}},
}

EXEMPT_BOTH = (
    "# accepted TICKET-1 — repo-scoped 1h token, no artifact upload\n"
    ".github/workflows/publish.yaml:push\n"
    ".github/workflows/deploy.yaml:push\n"
)


class TestWithoutExemptions(unittest.TestCase):
    def test_every_persisting_checkout_is_a_finding(self):
        check = check_persist_credentials(node([PUBLISH, DEPLOY, CI]))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("3 checkout step(s)", check.failure_reasons[0])

    def test_persist_credentials_false_passes(self):
        clean = {
            "file": ".github/workflows/ci.yaml",
            "jobs": {"build": {"steps": [checkout(persist=False)]}},
        }
        check = check_persist_credentials(node([clean]))
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertFalse(is_skipped(check))


class TestExemptJobs(unittest.TestCase):
    def test_exempted_jobs_leave_the_remaining_finding(self):
        with policy_vars(exempt_jobs=EXEMPT_BOTH):
            check = check_persist_credentials(node([PUBLISH, DEPLOY, CI]))
        self.assertEqual(check.status, CheckStatus.FAIL)
        reason = check.failure_reasons[0]
        self.assertIn("1 checkout step(s)", reason)
        self.assertIn("ci.yaml", reason)
        self.assertIn("2 exempted by exempt_jobs", reason)
        self.assertIn("publish.yaml:push", reason)

    def test_non_exempt_job_in_an_exempted_workflow_still_fails(self):
        two_jobs = {
            "file": ".github/workflows/publish.yaml",
            "jobs": {
                "push": {"steps": [checkout()]},
                "build": {"steps": [checkout()]},
            },
        }
        with policy_vars(
            exempt_jobs=".github/workflows/publish.yaml:push\n"
        ):
            check = check_persist_credentials(node([two_jobs]))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("job 'build'", check.failure_reasons[0])

    def test_all_exempted_skips_and_never_passes(self):
        with policy_vars(exempt_jobs=EXEMPT_BOTH):
            check = check_persist_credentials(node([PUBLISH, DEPLOY]))
        self.assertTrue(is_skipped(check))
        message = check._results[0].failure_message
        self.assertIn("2 checkout step(s)", message)
        self.assertIn("publish.yaml:push", message)
        self.assertIn("deploy.yaml:push", message)

    def test_a_comment_containing_a_comma_is_not_an_entry(self):
        # Comments are stripped per line before the comma split, or the tail of
        # a prose rationale parses as a second entry.
        with policy_vars(
            exempt_jobs=(
                "# accepted TICKET-1: repo-scoped token, no artifact upload\n"
                ".github/workflows/publish.yaml:push\n"
            )
        ):
            check = check_persist_credentials(node([PUBLISH]))
        self.assertTrue(is_skipped(check))

    def test_comma_separated_entries_are_accepted(self):
        with policy_vars(
            exempt_jobs=".github/workflows/publish.yaml:push,.github/workflows/deploy.yaml:push"
        ):
            check = check_persist_credentials(node([PUBLISH, DEPLOY]))
        self.assertTrue(is_skipped(check))

    def test_bare_filename_matches_the_collected_path(self):
        with policy_vars(exempt_jobs="publish.yaml:push\n"):
            check = check_persist_credentials(node([PUBLISH]))
        self.assertTrue(is_skipped(check))

    def test_comments_and_blank_lines_are_ignored(self):
        with policy_vars(
            exempt_jobs=(
                "# reviewed 2026-09-22\n\n"
                ".github/workflows/publish.yaml:push  # accepted TICKET-1\n"
            )
        ):
            check = check_persist_credentials(node([PUBLISH]))
        self.assertTrue(is_skipped(check))

    def test_two_checkouts_in_one_job_name_the_entry_once(self):
        twice = {
            "file": ".github/workflows/publish.yaml",
            "jobs": {"push": {"steps": [checkout("First"), checkout("Second")]}},
        }
        with policy_vars(
            exempt_jobs=".github/workflows/publish.yaml:push\n"
        ):
            check = check_persist_credentials(node([twice]))
        message = check._results[0].failure_message
        self.assertIn("2 checkout step(s)", message)
        self.assertEqual(message.count("publish.yaml:push"), 1)

    def test_unused_exemption_on_a_clean_job_passes(self):
        clean = {
            "file": ".github/workflows/publish.yaml",
            "jobs": {"push": {"steps": [checkout(persist=False)]}},
        }
        with policy_vars(
            exempt_jobs=".github/workflows/publish.yaml:push\n"
        ):
            check = check_persist_credentials(node([clean]))
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertFalse(is_skipped(check))


class TestStaleAndForeignEntries(unittest.TestCase):
    def test_entry_naming_a_job_the_workflow_lacks_is_reported(self):
        with policy_vars(
            exempt_jobs=".github/workflows/ci.yaml:publish\n"
        ):
            check = check_persist_credentials(node([CI]))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("ci.yaml:publish", check.failure_reasons[0])

    def test_a_stale_entry_survives_alongside_a_full_exemption(self):
        # skip() clears earlier results, so an all-exempted component must not
        # skip away a stale entry.
        with policy_vars(
            exempt_jobs=(
                EXEMPT_BOTH + ".github/workflows/publish.yaml:gone\n"
            )
        ):
            check = check_persist_credentials(node([PUBLISH, DEPLOY]))
        self.assertFalse(is_skipped(check))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("publish.yaml:gone", check.failure_reasons[0])

    def test_entry_for_a_workflow_this_component_lacks_is_ignored(self):
        # One policy entry is shared by every component in scope.
        with policy_vars(exempt_jobs=EXEMPT_BOTH):
            check = check_persist_credentials(node([CI]))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(len(check.failure_reasons), 1)
        self.assertIn("1 checkout step(s)", check.failure_reasons[0])


class TestMalformedInput(unittest.TestCase):
    def test_entry_without_a_job_raises(self):
        with policy_vars(exempt_jobs="ci.yaml\n"):
            with self.assertRaises(ValueError):
                check_persist_credentials(node([CI]))

    def test_entry_that_is_only_a_job_raises(self):
        with policy_vars(exempt_jobs=":build\n"):
            with self.assertRaises(ValueError):
                check_persist_credentials(node([CI]))

    def test_one_malformed_entry_exempts_nothing(self):
        with policy_vars(
            exempt_jobs=".github/workflows/publish.yaml:push,deploy.yaml\n"
        ):
            with self.assertRaises(ValueError):
                check_persist_credentials(node([PUBLISH, DEPLOY]))


class TestOtherChecksUnaffected(unittest.TestCase):
    def test_exempt_jobs_does_not_reach_permissions_declared(self):
        with policy_vars(exempt_jobs=EXEMPT_BOTH):
            check = check_permissions_declared(node([PUBLISH, DEPLOY]))
        self.assertEqual(check.status, CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
