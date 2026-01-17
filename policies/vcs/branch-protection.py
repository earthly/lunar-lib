from lunar_policy import Check, variable_or_default


def main():
    with Check("branch-protection", "Branch protection rules should be properly configured") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        # Check if branch protection should be enabled or disabled
        require_enabled = variable_or_default("require_enabled", None)
        if require_enabled is not None:
            try:
                require_enabled = require_enabled.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"require_enabled must be a boolean, got: {require_enabled}")

            enabled = bp.get_value_or_default(".enabled", False)
            branch = bp.get_value_or_default(".branch", "default branch")

            if require_enabled and not enabled:
                c.fail(f"Branch protection is not enabled on {branch}")
            elif not require_enabled and enabled:
                c.fail(f"Branch protection is enabled on {branch}, but policy requires it to be disabled")

        # Skip remaining checks if branch protection is not enabled
        if not bp.get_value_or_default(".enabled", False):
            return

        # Check if pull requests are required or not required
        require_pr = variable_or_default("require_pr", None)
        if require_pr is not None:
            try:
                require_pr = require_pr.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"require_pr must be a boolean, got: {require_pr}")

            has_pr_requirement = bp.get_value_or_default(".require_pr", False)
            if require_pr and not has_pr_requirement:
                c.fail("Branch protection does not require pull requests before merging")
            elif not require_pr and has_pr_requirement:
                c.fail("Branch protection requires pull requests, but policy requires PRs to not be required")

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

        # Check if code owner review is required or not required
        require_codeowner_review = variable_or_default("require_codeowner_review", None)
        if require_codeowner_review is not None:
            try:
                require_codeowner_review = require_codeowner_review.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"require_codeowner_review must be a boolean, got: {require_codeowner_review}")

            has_codeowner_review = bp.get_value_or_default(".require_codeowner_review", False)
            if require_codeowner_review and not has_codeowner_review:
                c.fail("Branch protection does not require code owner review")
            elif not require_codeowner_review and has_codeowner_review:
                c.fail("Branch protection requires code owner review, but policy requires it to not be required")

        # Check if stale reviews are dismissed or not dismissed
        require_dismiss_stale_reviews = variable_or_default("require_dismiss_stale_reviews", None)
        if require_dismiss_stale_reviews is not None:
            try:
                require_dismiss_stale_reviews = require_dismiss_stale_reviews.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"require_dismiss_stale_reviews must be a boolean, got: {require_dismiss_stale_reviews}")

            dismisses_stale = bp.get_value_or_default(".dismiss_stale_reviews", False)
            if require_dismiss_stale_reviews and not dismisses_stale:
                c.fail("Branch protection does not dismiss stale reviews when new commits are pushed")
            elif not require_dismiss_stale_reviews and dismisses_stale:
                c.fail("Branch protection dismisses stale reviews, but policy requires it to not dismiss them")

        # Check if status checks are required or not required
        require_status_checks = variable_or_default("require_status_checks", None)
        if require_status_checks is not None:
            try:
                require_status_checks = require_status_checks.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"require_status_checks must be a boolean, got: {require_status_checks}")

            has_status_checks = bp.get_value_or_default(".require_status_checks", False)
            if require_status_checks and not has_status_checks:
                c.fail("Branch protection does not require status checks to pass")
            elif not require_status_checks and has_status_checks:
                c.fail("Branch protection requires status checks, but policy requires them to not be required")

        # Check if branches must be up to date before merging or not
        require_up_to_date = variable_or_default("require_up_to_date", None)
        if require_up_to_date is not None:
            try:
                require_up_to_date = require_up_to_date.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"require_up_to_date must be a boolean, got: {require_up_to_date}")

            branches_up_to_date = bp.get_value_or_default(".require_branches_up_to_date", False)
            if require_up_to_date and not branches_up_to_date:
                c.fail("Branch protection does not require branches to be up to date before merging")
            elif not require_up_to_date and branches_up_to_date:
                c.fail("Branch protection requires branches to be up to date, but policy requires it to not be required")

        # Check force push setting (disallow means .allow_force_push should be false)
        disallow_force_push = variable_or_default("disallow_force_push", None)
        if disallow_force_push is not None:
            try:
                disallow_force_push = disallow_force_push.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"disallow_force_push must be a boolean, got: {disallow_force_push}")

            allows_force_push = bp.get_value_or_default(".allow_force_push", False)
            if disallow_force_push and allows_force_push:
                c.fail("Branch protection allows force pushes, but policy requires them to be disabled")
            elif not disallow_force_push and not allows_force_push:
                c.fail("Branch protection disallows force pushes, but policy requires them to be allowed")

        # Check deletion setting (disallow means .allow_deletions should be false)
        disallow_deletions = variable_or_default("disallow_deletions", None)
        if disallow_deletions is not None:
            try:
                disallow_deletions = disallow_deletions.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"disallow_deletions must be a boolean, got: {disallow_deletions}")

            allows_deletions = bp.get_value_or_default(".allow_deletions", False)
            if disallow_deletions and allows_deletions:
                c.fail("Branch protection allows branch deletion, but policy requires it to be disabled")
            elif not disallow_deletions and not allows_deletions:
                c.fail("Branch protection disallows branch deletion, but policy requires it to be allowed")

        # Check if linear history is required or not required
        require_linear_history = variable_or_default("require_linear_history", None)
        if require_linear_history is not None:
            try:
                require_linear_history = require_linear_history.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"require_linear_history must be a boolean, got: {require_linear_history}")

            has_linear_history = bp.get_value_or_default(".require_linear_history", False)
            if require_linear_history and not has_linear_history:
                c.fail("Branch protection does not require linear history")
            elif not require_linear_history and has_linear_history:
                c.fail("Branch protection requires linear history, but policy requires it to not be required")

        # Check if signed commits are required or not required
        require_signed_commits = variable_or_default("require_signed_commits", None)
        if require_signed_commits is not None:
            try:
                require_signed_commits = require_signed_commits.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"require_signed_commits must be a boolean, got: {require_signed_commits}")

            has_signed_commits = bp.get_value_or_default(".require_signed_commits", False)
            if require_signed_commits and not has_signed_commits:
                c.fail("Branch protection does not require signed commits")
            elif not require_signed_commits and has_signed_commits:
                c.fail("Branch protection requires signed commits, but policy requires them to not be required")


if __name__ == "__main__":
    main()
