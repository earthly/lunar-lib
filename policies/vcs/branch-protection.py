from lunar_policy import Check, variable_or_default


def main():
    with Check("branch-protection", "Branch protection rules should be properly configured") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        # Check if branch protection should be enabled
        require_enabled = variable_or_default("require_enabled", None)
        if require_enabled is not None:
            enabled = bp.get_value_or_default(".enabled", False)
            if require_enabled and not enabled:
                branch = bp.get_value_or_default(".branch", "default branch")
                c.fail(f"Branch protection is not enabled on {branch}")

        # Skip remaining checks if branch protection is not enabled
        if not bp.get_value_or_default(".enabled", False):
            return

        # Check if pull requests are required
        require_pr = variable_or_default("require_pr", None)
        if require_pr is not None:
            has_pr_requirement = bp.get_value_or_default(".require_pr", False)
            if require_pr and not has_pr_requirement:
                c.fail("Branch protection does not require pull requests before merging")

        # Check minimum number of required approvals
        min_approvals = variable_or_default("min_approvals", None)
        if min_approvals is not None:
            try:
                min_approvals = int(min_approvals)
                required_approvals = bp.get_value_or_default(".required_approvals", 0)
                if required_approvals < min_approvals:
                    c.fail(
                        f"Branch protection requires {required_approvals} approval(s), "
                        f"but policy requires at least {min_approvals}"
                    )
            except (ValueError, TypeError):
                raise ValueError(f"min_approvals must be a number, got: {min_approvals}")

        # Check if code owner review is required
        require_codeowner_review = variable_or_default("require_codeowner_review", None)
        if require_codeowner_review is not None:
            has_codeowner_review = bp.get_value_or_default(".require_codeowner_review", False)
            if require_codeowner_review and not has_codeowner_review:
                c.fail("Branch protection does not require code owner review")

        # Check if stale reviews are dismissed
        require_dismiss_stale_reviews = variable_or_default("require_dismiss_stale_reviews", None)
        if require_dismiss_stale_reviews is not None:
            dismisses_stale = bp.get_value_or_default(".dismiss_stale_reviews", False)
            if require_dismiss_stale_reviews and not dismisses_stale:
                c.fail("Branch protection does not dismiss stale reviews when new commits are pushed")

        # Check if status checks are required
        require_status_checks = variable_or_default("require_status_checks", None)
        if require_status_checks is not None:
            has_status_checks = bp.get_value_or_default(".require_status_checks", False)
            if require_status_checks and not has_status_checks:
                c.fail("Branch protection does not require status checks to pass")

        # Check if branches must be up to date before merging
        require_up_to_date = variable_or_default("require_up_to_date", None)
        if require_up_to_date is not None:
            branches_up_to_date = bp.get_value_or_default(".require_branches_up_to_date", False)
            if require_up_to_date and not branches_up_to_date:
                c.fail("Branch protection does not require branches to be up to date before merging")

        # Check that force pushes are disallowed
        disallow_force_push = variable_or_default("disallow_force_push", None)
        if disallow_force_push is not None:
            allows_force_push = bp.get_value_or_default(".allow_force_push", False)
            if disallow_force_push and allows_force_push:
                c.fail("Branch protection allows force pushes (should be disabled)")

        # Check that deletions are disallowed
        disallow_deletions = variable_or_default("disallow_deletions", None)
        if disallow_deletions is not None:
            allows_deletions = bp.get_value_or_default(".allow_deletions", False)
            if disallow_deletions and allows_deletions:
                c.fail("Branch protection allows branch deletion (should be disabled)")

        # Check if linear history is required
        require_linear_history = variable_or_default("require_linear_history", None)
        if require_linear_history is not None:
            has_linear_history = bp.get_value_or_default(".require_linear_history", False)
            if require_linear_history and not has_linear_history:
                c.fail("Branch protection does not require linear history")

        # Check if signed commits are required
        require_signed_commits = variable_or_default("require_signed_commits", None)
        if require_signed_commits is not None:
            has_signed_commits = bp.get_value_or_default(".require_signed_commits", False)
            if require_signed_commits and not has_signed_commits:
                c.fail("Branch protection does not require signed commits")


if __name__ == "__main__":
    main()
