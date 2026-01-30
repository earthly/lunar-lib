"""Unit tests for VCS policies.

These tests verify that the VCS policies correctly evaluate branch protection
settings and repository configuration. The tests help catch issues like:
- Typos in SDK method names (e.g., assert_equal vs assert_equals)
- Missing data handling
- Logic errors in policy assertions
"""

import unittest
from lunar_policy import Node, CheckStatus

# Import all policy main functions
# Note: Python files have hyphens in names, use importlib for clean imports
import importlib.util
import sys
from pathlib import Path

def load_policy(filename):
    """Load a policy module from a hyphenated filename."""
    policy_dir = Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_"), 
        policy_dir / f"{filename}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main

check_branch_protection_enabled = load_policy("branch-protection-enabled")
check_disallow_branch_deletion = load_policy("disallow-branch-deletion")
check_disallow_force_push = load_policy("disallow-force-push")
check_dismiss_stale_reviews = load_policy("dismiss-stale-reviews")
check_require_branches_up_to_date = load_policy("require-branches-up-to-date")
check_require_codeowner_review = load_policy("require-codeowner-review")
check_require_linear_history = load_policy("require-linear-history")
check_require_pull_request = load_policy("require-pull-request")
check_require_signed_commits = load_policy("require-signed-commits")
check_require_status_checks = load_policy("require-status-checks")
check_require_private = load_policy("require-private")
check_require_default_branch = load_policy("require-default-branch")
check_minimum_approvals = load_policy("minimum-approvals")
check_allowed_merge_strategies = load_policy("allowed-merge-strategies")


def make_branch_protection_data(
    enabled=True,
    branch="main",
    allow_deletions=False,
    allow_force_push=False,
    dismiss_stale_reviews=True,
    require_branches_up_to_date=True,
    require_codeowner_review=True,
    require_linear_history=True,
    require_pr=True,
    require_signed_commits=True,
    require_status_checks=True,
    required_approvals=2,
):
    """Helper to create branch protection test data."""
    return {
        "vcs": {
            "branch_protection": {
                "enabled": enabled,
                "branch": branch,
                "allow_deletions": allow_deletions,
                "allow_force_push": allow_force_push,
                "dismiss_stale_reviews": dismiss_stale_reviews,
                "require_branches_up_to_date": require_branches_up_to_date,
                "require_codeowner_review": require_codeowner_review,
                "require_linear_history": require_linear_history,
                "require_pr": require_pr,
                "require_signed_commits": require_signed_commits,
                "require_status_checks": require_status_checks,
                "required_approvals": required_approvals,
            }
        }
    }


class TestBranchProtectionEnabled(unittest.TestCase):
    """Tests for branch-protection-enabled policy."""

    def test_enabled_passes(self):
        """Branch protection enabled should pass."""
        data = make_branch_protection_data(enabled=True)
        node = Node.from_component_json(data)
        check = check_branch_protection_enabled(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_disabled_fails(self):
        """Branch protection disabled should fail."""
        data = make_branch_protection_data(enabled=False)
        node = Node.from_component_json(data)
        check = check_branch_protection_enabled(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])

    def test_missing_data_fails(self):
        """Missing VCS data should fail with clear message."""
        data = {}
        node = Node.from_component_json(data)
        check = check_branch_protection_enabled(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("VCS data not found", check.failure_reasons[0])


class TestDisallowBranchDeletion(unittest.TestCase):
    """Tests for disallow-branch-deletion policy."""

    def test_deletions_disallowed_passes(self):
        """Branch deletions disallowed should pass."""
        data = make_branch_protection_data(allow_deletions=False)
        node = Node.from_component_json(data)
        check = check_disallow_branch_deletion(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_deletions_allowed_fails(self):
        """Branch deletions allowed should fail."""
        data = make_branch_protection_data(allow_deletions=True)
        node = Node.from_component_json(data)
        check = check_disallow_branch_deletion(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("deletion", check.failure_reasons[0].lower())

    def test_protection_disabled_fails(self):
        """Disabled branch protection should fail."""
        data = make_branch_protection_data(enabled=False, allow_deletions=False)
        node = Node.from_component_json(data)
        check = check_disallow_branch_deletion(node)
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestDisallowForcePush(unittest.TestCase):
    """Tests for disallow-force-push policy."""

    def test_force_push_disallowed_passes(self):
        """Force push disallowed should pass."""
        data = make_branch_protection_data(allow_force_push=False)
        node = Node.from_component_json(data)
        check = check_disallow_force_push(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_force_push_allowed_fails(self):
        """Force push allowed should fail."""
        data = make_branch_protection_data(allow_force_push=True)
        node = Node.from_component_json(data)
        check = check_disallow_force_push(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("force push", check.failure_reasons[0].lower())


class TestDismissStaleReviews(unittest.TestCase):
    """Tests for dismiss-stale-reviews policy."""

    def test_stale_reviews_dismissed_passes(self):
        """Stale reviews dismissed should pass."""
        data = make_branch_protection_data(dismiss_stale_reviews=True)
        node = Node.from_component_json(data)
        check = check_dismiss_stale_reviews(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_stale_reviews_not_dismissed_fails(self):
        """Stale reviews not dismissed should fail."""
        data = make_branch_protection_data(dismiss_stale_reviews=False)
        node = Node.from_component_json(data)
        check = check_dismiss_stale_reviews(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("stale review", check.failure_reasons[0].lower())


class TestRequireBranchesUpToDate(unittest.TestCase):
    """Tests for require-branches-up-to-date policy."""

    def test_branches_up_to_date_required_passes(self):
        """Branches up to date required should pass."""
        data = make_branch_protection_data(require_branches_up_to_date=True)
        node = Node.from_component_json(data)
        check = check_require_branches_up_to_date(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_branches_up_to_date_not_required_fails(self):
        """Branches up to date not required should fail."""
        data = make_branch_protection_data(require_branches_up_to_date=False)
        node = Node.from_component_json(data)
        check = check_require_branches_up_to_date(node)
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestRequireCodeownerReview(unittest.TestCase):
    """Tests for require-codeowner-review policy."""

    def test_codeowner_review_required_passes(self):
        """Code owner review required should pass."""
        data = make_branch_protection_data(require_codeowner_review=True)
        node = Node.from_component_json(data)
        check = check_require_codeowner_review(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_codeowner_review_not_required_fails(self):
        """Code owner review not required should fail."""
        data = make_branch_protection_data(require_codeowner_review=False)
        node = Node.from_component_json(data)
        check = check_require_codeowner_review(node)
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestRequireLinearHistory(unittest.TestCase):
    """Tests for require-linear-history policy."""

    def test_linear_history_required_passes(self):
        """Linear history required should pass."""
        data = make_branch_protection_data(require_linear_history=True)
        node = Node.from_component_json(data)
        check = check_require_linear_history(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_linear_history_not_required_fails(self):
        """Linear history not required should fail."""
        data = make_branch_protection_data(require_linear_history=False)
        node = Node.from_component_json(data)
        check = check_require_linear_history(node)
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestRequirePullRequest(unittest.TestCase):
    """Tests for require-pull-request policy."""

    def test_pr_required_passes(self):
        """PR required should pass."""
        data = make_branch_protection_data(require_pr=True)
        node = Node.from_component_json(data)
        check = check_require_pull_request(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_pr_not_required_fails(self):
        """PR not required should fail."""
        data = make_branch_protection_data(require_pr=False)
        node = Node.from_component_json(data)
        check = check_require_pull_request(node)
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestRequireSignedCommits(unittest.TestCase):
    """Tests for require-signed-commits policy."""

    def test_signed_commits_required_passes(self):
        """Signed commits required should pass."""
        data = make_branch_protection_data(require_signed_commits=True)
        node = Node.from_component_json(data)
        check = check_require_signed_commits(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_signed_commits_not_required_fails(self):
        """Signed commits not required should fail."""
        data = make_branch_protection_data(require_signed_commits=False)
        node = Node.from_component_json(data)
        check = check_require_signed_commits(node)
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestRequireStatusChecks(unittest.TestCase):
    """Tests for require-status-checks policy."""

    def test_status_checks_required_passes(self):
        """Status checks required should pass."""
        data = make_branch_protection_data(require_status_checks=True)
        node = Node.from_component_json(data)
        check = check_require_status_checks(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_status_checks_not_required_fails(self):
        """Status checks not required should fail."""
        data = make_branch_protection_data(require_status_checks=False)
        node = Node.from_component_json(data)
        check = check_require_status_checks(node)
        self.assertEqual(check.status, CheckStatus.FAIL)


class TestRequirePrivate(unittest.TestCase):
    """Tests for require-private policy."""

    def test_private_repo_passes(self):
        """Private repository should pass."""
        data = {"vcs": {"visibility": "private"}}
        node = Node.from_component_json(data)
        check = check_require_private(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_public_repo_fails(self):
        """Public repository should fail."""
        data = {"vcs": {"visibility": "public"}}
        node = Node.from_component_json(data)
        check = check_require_private(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("public", check.failure_reasons[0])
        self.assertIn("private", check.failure_reasons[0])

    def test_missing_visibility_fails(self):
        """Missing visibility data should fail."""
        data = {}
        node = Node.from_component_json(data)
        check = check_require_private(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("VCS data not found", check.failure_reasons[0])


class TestRequireDefaultBranch(unittest.TestCase):
    """Tests for require-default-branch policy."""

    def test_main_branch_passes(self):
        """Default branch 'main' should pass with default config."""
        data = {"vcs": {"default_branch": "main"}}
        node = Node.from_component_json(data)
        check = check_require_default_branch(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_master_branch_fails(self):
        """Default branch 'master' should fail with default config."""
        data = {"vcs": {"default_branch": "master"}}
        node = Node.from_component_json(data)
        check = check_require_default_branch(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("master", check.failure_reasons[0])
        self.assertIn("main", check.failure_reasons[0])


class TestMinimumApprovals(unittest.TestCase):
    """Tests for minimum-approvals policy."""

    def test_enough_approvals_passes(self):
        """Enough required approvals should pass."""
        data = make_branch_protection_data(required_approvals=2)
        node = Node.from_component_json(data)
        check = check_minimum_approvals(node, min_approvals_override="2")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_more_than_minimum_passes(self):
        """More than minimum approvals should pass."""
        data = make_branch_protection_data(required_approvals=3)
        node = Node.from_component_json(data)
        check = check_minimum_approvals(node, min_approvals_override="2")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_less_than_minimum_fails(self):
        """Less than minimum approvals should fail."""
        data = make_branch_protection_data(required_approvals=1)
        node = Node.from_component_json(data)
        check = check_minimum_approvals(node, min_approvals_override="2")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("1", check.failure_reasons[0])
        self.assertIn("2", check.failure_reasons[0])

    def test_misconfiguration_raises_error(self):
        """Missing min_approvals config should raise ValueError."""
        data = make_branch_protection_data(required_approvals=2)
        node = Node.from_component_json(data)
        with self.assertRaises(ValueError) as context:
            check_minimum_approvals(node, min_approvals_override=None)
        self.assertIn("misconfiguration", str(context.exception))


class TestAllowedMergeStrategies(unittest.TestCase):
    """Tests for allowed-merge-strategies policy."""

    def test_only_squash_allowed_passes(self):
        """Only squash enabled when only squash allowed should pass."""
        data = {
            "vcs": {
                "merge_strategies": {
                    "allow_merge_commit": False,
                    "allow_squash_merge": True,
                    "allow_rebase_merge": False,
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_allowed_merge_strategies(node, allowed_strategies_override="squash")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_disallowed_strategy_enabled_fails(self):
        """Disallowed strategy enabled should fail."""
        data = {
            "vcs": {
                "merge_strategies": {
                    "allow_merge_commit": True,  # Not allowed
                    "allow_squash_merge": True,
                    "allow_rebase_merge": False,
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_allowed_merge_strategies(node, allowed_strategies_override="squash")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("Merge commits", check.failure_reasons[0])

    def test_multiple_allowed_strategies_pass(self):
        """Multiple allowed strategies with only those enabled should pass."""
        data = {
            "vcs": {
                "merge_strategies": {
                    "allow_merge_commit": False,
                    "allow_squash_merge": True,
                    "allow_rebase_merge": True,
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_allowed_merge_strategies(node, allowed_strategies_override="squash,rebase")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_invalid_strategy_raises_error(self):
        """Invalid strategy in config should raise ValueError."""
        data = {
            "vcs": {
                "merge_strategies": {
                    "allow_merge_commit": False,
                    "allow_squash_merge": True,
                    "allow_rebase_merge": False,
                }
            }
        }
        node = Node.from_component_json(data)
        with self.assertRaises(ValueError) as context:
            check_allowed_merge_strategies(node, allowed_strategies_override="invalid")
        self.assertIn("Invalid merge strategies", str(context.exception))

    def test_empty_config_raises_error(self):
        """Empty allowed_merge_strategies should raise ValueError."""
        data = {
            "vcs": {
                "merge_strategies": {
                    "allow_merge_commit": True,
                    "allow_squash_merge": True,
                    "allow_rebase_merge": True,
                }
            }
        }
        node = Node.from_component_json(data)
        with self.assertRaises(ValueError) as context:
            check_allowed_merge_strategies(node, allowed_strategies_override="")
        self.assertIn("must be configured", str(context.exception))


if __name__ == "__main__":
    unittest.main()
