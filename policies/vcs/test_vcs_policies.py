"""Unit tests for VCS policies.

These tests verify that the VCS policies correctly evaluate branch protection
settings and repository configuration. The tests help catch issues like:
- Typos in SDK method names (e.g., assert_equal vs assert_equals)
- Missing data handling
- Logic errors in policy assertions
"""

import os
import unittest
from unittest import mock
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
check_disallow_bypass_actors = load_policy("disallow-bypass-actors")
check_pr_commits_signed = load_policy("pr-commits-signed")
check_release_commits_merged_via_pr = load_policy("release-commits-merged-via-pr")


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
    source=None,
):
    """Helper to create branch protection test data."""
    bp = {
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
    if source is not None:
        bp["source"] = source
    return {"vcs": {"branch_protection": bp}}


def make_disabled_protection_data(branch="main"):
    """Helper to create disabled branch protection data.
    
    When branch protection is disabled, GitHub only returns enabled/branch
    without the detailed settings. This tests the real-world scenario.
    """
    return {
        "vcs": {
            "branch_protection": {
                "enabled": False,
                "branch": branch,
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
        """Missing VCS data should fail once collection has finished."""
        data = {}
        # workflows_finished=True models completed collection, where absent data
        # is a genuine violation (FAIL). During the interim it (correctly) PENDs
        # — see TestInterimPending below.
        node = Node.from_component_json(data, bundle_info={"workflows_finished": True})
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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_disallow_branch_deletion(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_disallow_force_push(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_dismiss_stale_reviews(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_require_branches_up_to_date(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_require_codeowner_review(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_require_linear_history(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_require_pull_request(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_require_signed_commits(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_require_status_checks(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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
        """Missing visibility data should fail once collection has finished."""
        data = {}
        node = Node.from_component_json(data, bundle_info={"workflows_finished": True})
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

    def test_protection_disabled_minimal_data_fails(self):
        """Disabled protection with minimal data should fail gracefully."""
        data = make_disabled_protection_data()
        node = Node.from_component_json(data)
        check = check_minimum_approvals(node, min_approvals_override="2")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])


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


class TestRulesetsDerivedData(unittest.TestCase):
    """Tests for branch protection data derived from GitHub rulesets.

    The collector queries the classic branch-protection endpoint first and falls
    back to /repos/{owner}/{repo}/rules/branches/{branch} when the classic
    endpoint 404s. Either path produces the same .vcs.branch_protection schema,
    distinguished only by the .source field ("classic" | "ruleset" | "none").

    These tests verify policies evaluate correctly against the ruleset-derived
    shape — a repo with a ruleset enforcing PR + non_fast_forward + deletion
    should pass branch-protection-enabled, disallow-force-push, and
    disallow-branch-deletion even though it 404s on the classic endpoint.
    """

    def test_ruleset_protected_passes_enabled_check(self):
        """Ruleset-only protection should pass branch-protection-enabled."""
        data = make_branch_protection_data(enabled=True, source="ruleset")
        node = Node.from_component_json(data)
        check = check_branch_protection_enabled(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_ruleset_with_non_fast_forward_disallows_force_push(self):
        """Ruleset with non_fast_forward rule => allow_force_push=false => passes."""
        data = make_branch_protection_data(
            allow_force_push=False, source="ruleset"
        )
        node = Node.from_component_json(data)
        check = check_disallow_force_push(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_ruleset_with_deletion_rule_disallows_deletion(self):
        """Ruleset with deletion rule => allow_deletions=false => passes."""
        data = make_branch_protection_data(
            allow_deletions=False, source="ruleset"
        )
        node = Node.from_component_json(data)
        check = check_disallow_branch_deletion(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_ruleset_with_pr_rule_satisfies_minimum_approvals(self):
        """Ruleset with pull_request rule should populate required_approvals."""
        data = make_branch_protection_data(
            required_approvals=2, require_pr=True, source="ruleset"
        )
        node = Node.from_component_json(data)
        check = check_minimum_approvals(node, min_approvals_override=2)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_source_none_unprotected_fails(self):
        """Repo with neither classic nor ruleset protection => fails."""
        data = {
            "vcs": {
                "branch_protection": {
                    "enabled": False,
                    "branch": "main",
                    "source": "none",
                }
            }
        }
        node = Node.from_component_json(data)
        check = check_branch_protection_enabled(node)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_charts_repro_shape_passes(self):
        """Charts-shaped data (the repro case from ENG-741) should pass."""
        # Mirrors the field values the collector derives from the
        # earthly/charts ruleset: pull_request rule with 1 approval, non_fast_
        # forward + deletion present, no status checks, no signed commits.
        data = {
            "vcs": {
                "branch_protection": {
                    "enabled": True,
                    "source": "ruleset",
                    "branch": "main",
                    "require_pr": True,
                    "required_approvals": 1,
                    "require_codeowner_review": False,
                    "dismiss_stale_reviews": False,
                    "require_status_checks": False,
                    "require_branches_up_to_date": False,
                    "allow_force_push": False,
                    "allow_deletions": False,
                    "require_linear_history": False,
                    "require_signed_commits": False,
                    "required_checks": [],
                    "restrictions": {"users": [], "teams": [], "apps": []},
                }
            }
        }
        node = Node.from_component_json(data)
        self.assertEqual(
            check_branch_protection_enabled(node).status, CheckStatus.PASS
        )
        self.assertEqual(
            check_disallow_force_push(node).status, CheckStatus.PASS
        )
        self.assertEqual(
            check_disallow_branch_deletion(node).status, CheckStatus.PASS
        )
        self.assertEqual(
            check_require_pull_request(node).status, CheckStatus.PASS
        )


class TestInterimPending(unittest.TestCase):
    """ENG-1114: absent VCS data during the collection interim must PEND, not FAIL.

    The github collector may not have reported yet when a policy first runs.
    With workflows_finished=False the checks must render PENDING (⏳), only
    resolving to FAIL once collection has finished (see test_missing_data_fails).
    """

    def test_missing_data_pends_during_interim(self):
        node = Node.from_component_json({}, bundle_info={"workflows_finished": False})
        self.assertEqual(
            check_branch_protection_enabled(node).status, CheckStatus.PENDING
        )

    def test_missing_visibility_pends_during_interim(self):
        node = Node.from_component_json({}, bundle_info={"workflows_finished": False})
        self.assertEqual(check_require_private(node).status, CheckStatus.PENDING)


class TestGitLabNormalizedData(unittest.TestCase):
    """ENG-1474: the gitlab collector normalizes GitLab settings into the same
    .vcs.* schema as github, so these shared checks must evaluate GitLab-sourced
    data identically. A well-protected GitLab repo should pass every check that
    has a GitLab analog. (require-branches-up-to-date has no GitLab equivalent —
    GitLab does not populate the field — so it is intentionally github-only.)
    """

    GITLAB_DATA = {
        "vcs": {
            "provider": "gitlab",
            "visibility": "private",
            "default_branch": "main",
            "merge_strategies": {
                "allow_merge_commit": False,
                "allow_squash_merge": True,
                "allow_rebase_merge": True,
            },
            "branch_protection": {
                "enabled": True,
                "source": "gitlab",
                "branch": "main",
                "require_pr": True,
                "required_approvals": 2,
                "require_codeowner_review": True,
                "dismiss_stale_reviews": True,
                "require_status_checks": True,
                "required_checks": ["security-gate"],
                "require_signed_commits": True,
                "require_linear_history": True,
                "allow_force_push": False,
                "allow_deletions": False,
                "restrictions": {
                    "push_access_level": "maintainer",
                    "merge_access_level": "developer",
                },
            },
        }
    }

    def _node(self):
        return Node.from_component_json(
            self.GITLAB_DATA, bundle_info={"workflows_finished": True}
        )

    def test_analogous_checks_pass_on_gitlab_data(self):
        cases = [
            check_branch_protection_enabled(self._node()),
            check_require_pull_request(self._node()),
            check_minimum_approvals(self._node(), min_approvals_override="2"),
            check_require_codeowner_review(self._node()),
            check_dismiss_stale_reviews(self._node()),
            check_require_status_checks(self._node()),
            check_require_signed_commits(self._node()),
            check_require_linear_history(self._node()),
            check_disallow_force_push(self._node()),
            check_disallow_branch_deletion(self._node()),
            check_allowed_merge_strategies(
                self._node(), allowed_strategies_override="squash,rebase"
            ),
            check_require_private(self._node()),
            check_require_default_branch(self._node()),
        ]
        for check in cases:
            self.assertEqual(
                check.status, CheckStatus.PASS,
                f"{check.name} should PASS on GitLab data, got {check.status.name}: "
                f"{getattr(check, 'failure_reasons', None)}",
            )


# The shapes below are what collectors/github writes (see its tests and README).
RULESET_MAIN = {
    "id": 42, "name": "main", "source_type": "Repository", "source": "acme/widget",
    "bypass_actors": [
        {"actor_type": "OrganizationAdmin", "bypass_mode": "always"},
        {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"},
    ],
}
RULESET_EMPTY = {"id": 43, "name": "default", "source_type": "Repository",
                 "source": "acme/widget", "bypass_actors": []}
RULESET_HIDDEN = {"id": 73, "name": "org baseline", "source_type": "Organization", "source": "acme"}


def finished(data):
    return Node.from_component_json(data, bundle_info={"workflows_finished": True})


def skip_reason(check):
    """Check.status folds SKIPPED into PASS; read the recorded result instead."""
    if len(check._results) == 1 and check._results[0].result == CheckStatus.SKIPPED:
        return check._results[0].failure_message
    return None


def ruleset_protection(*rulesets):
    data = make_branch_protection_data(source="ruleset")
    data["vcs"]["branch_protection"]["rulesets"] = list(rulesets)
    return data


def classic_protection(enforce_admins=True, users=(), teams=(), apps=(), rulesets=()):
    data = make_branch_protection_data(source="classic")
    bp = data["vcs"]["branch_protection"]
    bp["enforce_admins"] = enforce_admins
    bp["bypass_pull_request_allowances"] = {"users": list(users), "teams": list(teams), "apps": list(apps)}
    bp["rulesets"] = list(rulesets)
    return data


class TestDisallowBypassActors(unittest.TestCase):
    """Tests for disallow-bypass-actors policy."""

    def test_rulesets_without_bypass_actors_pass(self):
        check = check_disallow_bypass_actors(finished(ruleset_protection(RULESET_EMPTY)), allowed_override="")
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertIsNone(skip_reason(check))

    def test_ruleset_bypass_actors_fail(self):
        check = check_disallow_bypass_actors(finished(ruleset_protection(RULESET_MAIN, RULESET_EMPTY)), allowed_override="")
        self.assertEqual(check.status, CheckStatus.FAIL)
        msg = check.failure_reasons[0]
        self.assertIn("Branch protection on main can be bypassed", msg)
        self.assertIn("\n    * ruleset 'main' (acme/widget) lets OrganizationAdmin bypass it (always)", msg)
        self.assertIn("\n    * ruleset 'main' (acme/widget) lets RepositoryRole 5 bypass it (always)", msg)

    def test_allowed_actors_are_accepted(self):
        allowed = """
            OrganizationAdmin     # break-glass, reviewed quarterly
            RepositoryRole:5      # repo admins, see TICKET-1, TICKET-2
        """
        check = check_disallow_bypass_actors(finished(ruleset_protection(RULESET_MAIN)), allowed_override=allowed)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_allow_list_matches_type_and_id(self):
        # RepositoryRole:4 is not RepositoryRole 5; a bare type allows every id.
        check = check_disallow_bypass_actors(
            finished(ruleset_protection(RULESET_MAIN)), allowed_override="organizationadmin, RepositoryRole:4")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertNotIn("OrganizationAdmin", check.failure_reasons[0])
        self.assertIn("RepositoryRole 5", check.failure_reasons[0])

    def test_hidden_bypass_list_skips(self):
        check = check_disallow_bypass_actors(finished(ruleset_protection(RULESET_EMPTY, RULESET_HIDDEN)), allowed_override="")
        reason = skip_reason(check)
        self.assertIsNotNone(reason)
        self.assertIn("ruleset 'org baseline' (acme)", reason)
        self.assertIn("write access", reason)

    def test_visible_violation_fails_even_when_another_list_is_hidden(self):
        check = check_disallow_bypass_actors(finished(ruleset_protection(RULESET_HIDDEN, RULESET_MAIN)), allowed_override="")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIsNone(skip_reason(check))

    def test_classic_admins_not_enforced_fails(self):
        check = check_disallow_bypass_actors(finished(classic_protection(enforce_admins=False)), allowed_override="")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("does not apply to administrators", check.failure_reasons[0])

    def test_classic_bypass_allowances_fail_unless_allowed(self):
        data = classic_protection(users=["jdoe"], teams=["release-managers"], apps=["release-bot"])
        check = check_disallow_bypass_actors(finished(data), allowed_override="")
        self.assertEqual(check.status, CheckStatus.FAIL)
        for who in ("User jdoe", "Team release-managers", "Integration release-bot"):
            self.assertIn(f"lets {who} bypass the pull-request requirement", check.failure_reasons[0])
        check = check_disallow_bypass_actors(
            finished(data), allowed_override="User:jdoe\nTeam:release-managers\nIntegration:release-bot")
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_classic_enforced_without_allowances_passes(self):
        check = check_disallow_bypass_actors(finished(classic_protection()), allowed_override="")
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertIsNone(skip_reason(check))

    def test_classic_rulesets_are_checked_too(self):
        check = check_disallow_bypass_actors(finished(classic_protection(rulesets=[RULESET_MAIN])), allowed_override="")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("ruleset 'main'", check.failure_reasons[0])

    def test_classic_violation_fails_when_rulesets_were_not_read(self):
        data = classic_protection(enforce_admins=False)
        del data["vcs"]["branch_protection"]["rulesets"]
        check = check_disallow_bypass_actors(finished(data), allowed_override="")
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_no_ruleset_data_skips(self):
        # An older github collector: the bypass lists were never read.
        check = check_disallow_bypass_actors(finished(make_branch_protection_data(source="ruleset")), allowed_override="")
        self.assertIn("rulesets on the branch", skip_reason(check))

    def test_gitlab_data_skips(self):
        check = check_disallow_bypass_actors(finished(TestGitLabNormalizedData.GITLAB_DATA), allowed_override="")
        self.assertIn("rulesets on the branch", skip_reason(check))

    def test_protection_disabled_fails(self):
        check = check_disallow_bypass_actors(finished(make_disabled_protection_data()), allowed_override="")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not enabled", check.failure_reasons[0])

    def test_missing_vcs_data_fails_once_collection_finished(self):
        check = check_disallow_bypass_actors(finished({}), allowed_override="")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("VCS data not found", check.failure_reasons[0])

    def test_pending_while_collection_runs(self):
        data = make_branch_protection_data(source="ruleset")
        node = Node.from_component_json(data, bundle_info={"workflows_finished": False})
        check = check_disallow_bypass_actors(node, allowed_override="")
        self.assertEqual(check.status, CheckStatus.PENDING)

    def test_malformed_allow_list_errors(self):
        # Raised (the check errors) rather than skipped, so a typo allows nothing.
        for bad in ("Team:", ":5", "Integration: , OrganizationAdmin"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    check_disallow_bypass_actors(finished(ruleset_protection(RULESET_MAIN)), allowed_override=bad)

    def test_allow_list_is_read_from_the_policy_input(self):
        with mock.patch.dict(os.environ, {"LUNAR_VAR_allowed_bypass_actors": "OrganizationAdmin,RepositoryRole:5"}):
            check = check_disallow_bypass_actors(finished(ruleset_protection(RULESET_MAIN)))
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_many_violations_are_capped(self):
        many = dict(RULESET_MAIN, bypass_actors=[
            {"actor_type": "Team", "actor_id": i, "bypass_mode": "always"} for i in range(15)])
        check = check_disallow_bypass_actors(finished(ruleset_protection(many)), allowed_override="")
        self.assertIn("+5 more", check.failure_reasons[0])


def pr_data(commits):
    return {"vcs": {"pr": {"number": 7, "title": "Add feature", "commits": commits}}}


SIGNED = {"sha": "4b7e1d9c2a5f8e3b6d0c9a1f7e2d5b8c4a3f6e19", "author": "jdoe",
          "signature": {"verified": True, "reason": "valid"}}
UNSIGNED = {"sha": "9f1c2e7d4b8a6f3e0c5d2b1a7e4f8c3d6b9a0e21",
            "signature": {"verified": False, "reason": "unsigned"}}


class TestPrCommitsSigned(unittest.TestCase):
    """Tests for pr-commits-signed policy."""

    def test_all_verified_passes(self):
        check = check_pr_commits_signed(finished(pr_data([SIGNED])))
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertIsNone(skip_reason(check))

    def test_unverified_commit_fails(self):
        bad_key = {"sha": "0" * 40, "signature": {"verified": False, "reason": "unknown_key"}}
        check = check_pr_commits_signed(finished(pr_data([SIGNED, UNSIGNED, bad_key])))
        self.assertEqual(check.status, CheckStatus.FAIL)
        msg = check.failure_reasons[0]
        self.assertIn("2 of 3 commit(s) have no verified signature", msg)
        self.assertIn("\n    * 9f1c2e7d4b8a (unsigned)", msg)
        self.assertIn("\n    * 000000000000 (unknown_key)", msg)

    def test_commit_without_verification_data_fails(self):
        check = check_pr_commits_signed(finished(pr_data([{"sha": "1" * 40}])))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("no verification data", check.failure_reasons[0])

    def test_no_commit_data_skips(self):
        check = check_pr_commits_signed(finished({"vcs": {"pr": {"number": 7}}}))
        self.assertIn("No commit signature data", skip_reason(check))

    def test_commit_count_instead_of_list_skips(self):
        check = check_pr_commits_signed(finished({"vcs": {"pr": {"number": 7, "commits": 3}}}))
        self.assertIn("not a list", skip_reason(check))

    def test_outside_a_pr_skips(self):
        check = check_pr_commits_signed(finished(make_branch_protection_data()))
        self.assertIn("No pull request data", skip_reason(check))

    def test_pending_while_collection_runs(self):
        node = Node.from_component_json({"vcs": {"pr": {"number": 7}}}, bundle_info={"workflows_finished": False})
        self.assertEqual(check_pr_commits_signed(node).status, CheckStatus.PENDING)


def release_data(commits, base=True, truncated=False, total=None):
    rr = {"tag_pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$", "head_sha": "c" * 40}
    if base:
        rr.update({"default_branch": "main", "base": {"tag": "v1.1.0", "sha": "e" * 40},
                   "total_commits": total if total is not None else len(commits),
                   "truncated": truncated, "commits": commits})
    return {"vcs": {"release_range": rr}}


MERGED = {"sha": "a7c0f3e6d9b2a5c8f1e4d7b0a3c6f9e2d5b8a1c4", "author": "jdoe",
          "signature": {"verified": True, "reason": "valid"},
          "pull_request": {"number": 41, "base_branch": "main", "head_branch": "feature/payments",
                           "merged_at": "2024-05-02T16:02:13Z",
                           "approvals": [{"reviewer": "alice", "submitted_at": "2024-05-02T15:40:51Z"}]}}
DIRECT = {"sha": "6d9b2e5a8c1f4d7b0e3a6c9f2d5b8e1a4c7f0d3b", "author": "github-actions[bot]",
          "signature": {"verified": False, "reason": "unsigned"}}


def commit_via(sha, number, base, head, merged):
    return {"sha": sha, "author": "jdoe", "signature": {"verified": True, "reason": "valid"},
            "pull_request": {"number": number, "base_branch": base, "head_branch": head,
                             "merged_at": merged, "approvals": []}}


class TestReleaseCommitsMergedViaPr(unittest.TestCase):
    """Tests for release-commits-merged-via-pr policy."""

    def test_every_commit_merged_passes(self):
        check = check_release_commits_merged_via_pr(finished(release_data([MERGED])))
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertIsNone(skip_reason(check))

    def test_direct_push_fails(self):
        check = check_release_commits_merged_via_pr(finished(release_data([MERGED, DIRECT])))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(
            check.failure_reasons[0],
            "1 commit(s) since v1.1.0 did not reach main through a merged pull request:"
            "\n    * 6d9b2e5a8c1f by github-actions[bot]: no merged pull request",
        )

    def test_gitflow_release_passes(self):
        # GitHub links a feature commit only to its PR into develop; the release
        # PR from develop into main, merged later, carried it on.
        feature = commit_via("1" * 40, 38, base="develop", head="feature/x", merged="2024-05-01T10:00:00Z")
        release = commit_via("2" * 40, 40, base="main", head="develop", merged="2024-05-02T10:00:00Z")
        check = check_release_commits_merged_via_pr(finished(release_data([feature, release])))
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertIsNone(skip_reason(check))

    def test_branch_pushed_straight_to_default_fails(self):
        # PRs merge into develop, then develop is pushed to main with no PR.
        feature = commit_via("3" * 40, 539, base="develop", head="feature/y", merged="2024-05-01T10:00:00Z")
        check = check_release_commits_merged_via_pr(finished(release_data([feature])))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn(
            "\n    * 333333333333 by jdoe: merged into develop by #539, which no later pull request carried into main",
            check.failure_reasons[0])

    def test_release_pr_merged_before_the_commit_does_not_carry_it(self):
        release = commit_via("2" * 40, 40, base="main", head="develop", merged="2024-05-01T10:00:00Z")
        later = commit_via("4" * 40, 41, base="develop", head="feature/z", merged="2024-05-03T10:00:00Z")
        check = check_release_commits_merged_via_pr(finished(release_data([release, later])))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("444444444444", check.failure_reasons[0])
        self.assertNotIn("222222222222", check.failure_reasons[0])

    def test_chain_of_branches_passes(self):
        commits = [
            commit_via("5" * 40, 50, base="develop-2", head="feature/a", merged="2024-05-01T10:00:00Z"),
            commit_via("6" * 40, 51, base="develop", head="develop-2", merged="2024-05-02T10:00:00Z"),
            commit_via("7" * 40, 52, base="main", head="develop", merged="2024-05-03T10:00:00Z"),
        ]
        check = check_release_commits_merged_via_pr(finished(release_data(commits)))
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_untraced_commit_in_truncated_range_is_unknown_not_failed(self):
        # The release PR that carried it may be among the commits not recorded.
        feature = commit_via("3" * 40, 539, base="develop", head="feature/y", merged="2024-05-01T10:00:00Z")
        check = check_release_commits_merged_via_pr(finished(release_data([feature], truncated=True, total=400)))
        self.assertIn("Only 1 of 400 commits since v1.1.0 were recorded", skip_reason(check))

    def test_range_longer_than_github_lists_says_so(self):
        check = check_release_commits_merged_via_pr(finished(release_data([MERGED], truncated=True, total=4078)))
        self.assertIn("GitHub lists at most 1000 commits", skip_reason(check))

    def test_range_without_commits_skips(self):
        check = check_release_commits_merged_via_pr(finished(release_data([])))
        self.assertIn("without its commits", skip_reason(check))

    def test_truncated_range_fails_on_what_it_saw(self):
        check = check_release_commits_merged_via_pr(finished(release_data([DIRECT], truncated=True, total=400)))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("(checked 1 of 400)", check.failure_reasons[0])

    def test_truncated_clean_range_skips(self):
        check = check_release_commits_merged_via_pr(finished(release_data([MERGED], truncated=True, total=400)))
        self.assertIn("Only 1 of 400 commits since v1.1.0 were recorded", skip_reason(check))
        self.assertIn("Raise release_range_max_commits", skip_reason(check))

    def test_no_previous_release_skips(self):
        check = check_release_commits_merged_via_pr(finished(release_data([], base=False)))
        self.assertIn("No release tag matching", skip_reason(check))

    def test_not_collected_skips(self):
        check = check_release_commits_merged_via_pr(finished(make_branch_protection_data()))
        self.assertIn("Set release_tag_pattern", skip_reason(check))

    def test_pending_while_collection_runs(self):
        node = Node.from_component_json({}, bundle_info={"workflows_finished": False})
        self.assertEqual(check_release_commits_merged_via_pr(node).status, CheckStatus.PENDING)

    def test_many_failures_are_capped(self):
        commits = [dict(DIRECT, sha=f"{i:040x}") for i in range(12)]
        check = check_release_commits_merged_via_pr(finished(release_data(commits)))
        self.assertIn("12 commit(s)", check.failure_reasons[0])
        self.assertIn("+2 more", check.failure_reasons[0])


if __name__ == "__main__":
    unittest.main()
