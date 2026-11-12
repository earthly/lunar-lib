"""Unit tests for actions-locked."""

import importlib.util
import sys
import unittest
from pathlib import Path

from lunar_policy import CheckStatus, Node


def load_policy(filename):
    spec = importlib.util.spec_from_file_location(
        filename, Path(__file__).parent / f"{filename}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


check_actions_locked = load_policy("actions_locked")

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"


def action(uses, pinning, party="3rd"):
    name, _, ref = uses.partition("@")
    return {"name": name, "ref": ref, "uses": uses, "pinning": pinning, "party": party}


def workflow(actions, file=".github/workflows/ci.yml"):
    return {"file": file, "actions": actions}


def run(workflows, lockfile=None, finished=True):
    gha = {"workflows": workflows}
    if lockfile is not None:
        gha["lockfile"] = lockfile
    return check_actions_locked(
        Node.from_component_json(
            {"ci": {"native": {"github_actions": gha}}},
            {"workflows_finished": finished},
        )
    )


def lock(workflows):
    return {"path": ".github/workflows/actions.lock", "version": "v0.0.3", "workflows": workflows}


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def is_skipped(check):
    """check.status never returns SKIPPED; a skip is recorded as a SKIPPED result."""
    return any(r.result == CheckStatus.SKIPPED for r in check._results)


class TestPinnedBySha(unittest.TestCase):
    def test_sha_pin_passes_without_a_lockfile(self):
        check = run([workflow([action(f"actions/checkout@{SHA}", "sha")])])
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertFalse(is_skipped(check))

    def test_tag_without_a_lockfile_fails(self):
        check = run([workflow([action("actions/checkout@v4", "tag")])])
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(
            failures(check),
            [
                "'.github/workflows/ci.yml' uses 'actions/checkout@v4', which isn't "
                "pinned to a commit. Pin it to a full-length commit SHA, or lock it "
                "with gh actions-lock."
            ],
        )

    def test_branch_and_unpinned_refs_fail(self):
        check = run(
            [
                workflow(
                    [
                        action("docker/login-action@main", "branch"),
                        action("some/action", "unpinned"),
                    ]
                )
            ]
        )
        self.assertEqual(len(failures(check)), 2)

    def test_one_failure_per_offending_reference(self):
        check = run(
            [
                workflow(
                    [
                        action("actions/checkout@v4", "tag"),
                        action("actions/checkout@v4", "tag"),
                        action("actions/setup-go@v6", "tag"),
                    ]
                ),
                workflow([action("actions/checkout@v4", "tag")], file=".github/workflows/release.yml"),
            ]
        )
        reasons = failures(check)
        self.assertEqual(len(reasons), 3)
        self.assertEqual(sum("release.yml" in r for r in reasons), 1)


class TestLockfile(unittest.TestCase):
    def test_tag_locked_for_its_workflow_passes(self):
        check = run(
            [workflow([action("actions/checkout@v7.0.1", "tag")])],
            lock({".github/workflows/ci.yml": ["actions/checkout@v7.0.1"]}),
        )
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_branch_locked_for_its_workflow_passes(self):
        # The lockfile pins the commit a branch resolved to, the same as a tag.
        check = run(
            [workflow([action("org/action@main", "branch")])],
            lock({".github/workflows/ci.yml": ["org/action@main"]}),
        )
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_reference_missing_from_the_lockfile_fails(self):
        # A step added without rerunning gh actions-lock.
        check = run(
            [
                workflow(
                    [
                        action("actions/checkout@v7.0.1", "tag"),
                        action("docker/login-action@v4", "tag"),
                    ]
                )
            ],
            lock({".github/workflows/ci.yml": ["actions/checkout@v7.0.1"]}),
        )
        reasons = failures(check)
        self.assertEqual(len(reasons), 1)
        self.assertIn("'docker/login-action@v4'", reasons[0])

    def test_changed_ref_fails(self):
        check = run(
            [workflow([action("actions/checkout@v7", "tag")])],
            lock({".github/workflows/ci.yml": ["actions/checkout@v7.0.1"]}),
        )
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_lock_entry_for_another_workflow_does_not_count(self):
        check = run(
            [workflow([action("actions/checkout@v4", "tag")], file=".github/workflows/new.yml")],
            lock({".github/workflows/ci.yml": ["actions/checkout@v4"]}),
        )
        reasons = failures(check)
        self.assertEqual(len(reasons), 1)
        self.assertIn("new.yml", reasons[0])

    def test_owner_and_repo_match_case_insensitively(self):
        # gh actions-lock lowercases owner/repo; workflows keep the publisher's case.
        check = run(
            [workflow([action("Swatinem/rust-cache@v2.9.3", "tag")])],
            lock({".github/workflows/ci.yml": ["swatinem/rust-cache@v2.9.3"]}),
        )
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_sub_path_action_is_locked_by_its_repository(self):
        check = run(
            [workflow([action("github/codeql-action/upload-sarif@v4.39.1", "tag")])],
            lock({".github/workflows/ci.yml": ["github/codeql-action@v4.39.1"]}),
        )
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_tag_case_still_matters(self):
        check = run(
            [workflow([action("actions/checkout@V4", "branch")])],
            lock({".github/workflows/ci.yml": ["actions/checkout@v4"]}),
        )
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_lockfile_without_workflows_locks_nothing(self):
        check = run(
            [workflow([action("actions/checkout@v4", "tag")])],
            {"path": ".github/workflows/actions.lock", "version": "v0.0.3"},
        )
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestReusableWorkflows(unittest.TestCase):
    def test_reusable_workflow_by_tag_fails_even_when_listed(self):
        uses = "org/shared/.github/workflows/build.yml@v1"
        check = run(
            [workflow([action(uses, "tag")])],
            lock({".github/workflows/ci.yml": [uses]}),
        )
        reasons = failures(check)
        self.assertEqual(len(reasons), 1)
        self.assertIn(f"calls '{uses}'", reasons[0])
        self.assertIn("doesn't cover reusable workflows", reasons[0])

    def test_reusable_workflow_by_sha_passes(self):
        check = run([workflow([action(f"org/shared/.github/workflows/build.yml@{SHA}", "sha")])])
        self.assertEqual(check.status, CheckStatus.PASS)


class TestScope(unittest.TestCase):
    def test_first_party_actions_are_not_checked(self):
        check = run([workflow([action("acme/setup@main", "branch", party="1st")])])
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_workflows_without_actions_pass(self):
        check = run([{"file": ".github/workflows/ci.yml", "actions": []}, {"file": ".github/workflows/x.yml"}])
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertFalse(is_skipped(check))

    def test_no_github_actions_data_skips(self):
        check = check_actions_locked(Node.from_component_json({}, {"workflows_finished": True}))
        self.assertTrue(is_skipped(check))

    def test_pending_while_collection_runs(self):
        check = check_actions_locked(Node.from_component_json({}, {"workflows_finished": False}))
        self.assertEqual(check.status, CheckStatus.PENDING)

    def test_present_data_without_a_lockfile_does_not_pend(self):
        check = run([workflow([action("actions/checkout@v4", "tag")])], finished=False)
        self.assertEqual(check.status, CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
