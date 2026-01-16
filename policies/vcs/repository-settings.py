from lunar_policy import Check, variable_or_default


def main():
    with Check("repository-settings", "Repository settings should meet organizational standards") as c:
        vcs = c.get_node(".vcs")

        if not vcs.exists():
            c.skip("No VCS data collected")

        # Check repository visibility
        allowed_visibility = variable_or_default("allowed_visibility", None)
        if allowed_visibility is not None:
            allowed_list = [v.strip() for v in allowed_visibility.split(",") if v.strip()]
            if not allowed_list:
                raise ValueError(
                    "Policy misconfiguration: 'allowed_visibility' is empty. "
                    "An allow-list must contain at least one entry. "
                    "Configure allowed visibility levels (e.g., 'private,internal') or exclude this check."
                )

            visibility = vcs.get_value_or_default(".visibility", None)
            if visibility and visibility not in allowed_list:
                c.fail(f"Repository visibility '{visibility}' is not in allowed list: {', '.join(allowed_list)}")

        # Check default branch name
        required_default_branch = variable_or_default("required_default_branch", None)
        if required_default_branch is not None:
            default_branch = vcs.get_value_or_default(".default_branch", None)
            if default_branch and default_branch != required_default_branch:
                c.fail(f"Default branch is '{default_branch}', but policy requires '{required_default_branch}'")

        # Check merge strategies
        merge_strategies = vcs.get_node(".merge_strategies")
        if not merge_strategies.exists():
            # If merge strategies data doesn't exist, skip these checks
            return

        # Check if merge commits should be allowed
        allow_merge_commit = variable_or_default("allow_merge_commit", None)
        if allow_merge_commit is not None:
            try:
                allow_merge_commit = allow_merge_commit.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"allow_merge_commit must be a boolean, got: {allow_merge_commit}")

            actual = merge_strategies.get_value_or_default(".allow_merge_commit", False)
            if allow_merge_commit and not actual:
                c.fail("Merge commits are disabled, but policy requires them to be allowed")
            elif not allow_merge_commit and actual:
                c.fail("Merge commits are allowed, but policy requires them to be disabled")

        # Check if squash merges should be allowed
        allow_squash_merge = variable_or_default("allow_squash_merge", None)
        if allow_squash_merge is not None:
            try:
                allow_squash_merge = allow_squash_merge.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"allow_squash_merge must be a boolean, got: {allow_squash_merge}")

            actual = merge_strategies.get_value_or_default(".allow_squash_merge", False)
            if allow_squash_merge and not actual:
                c.fail("Squash merges are disabled, but policy requires them to be allowed")
            elif not allow_squash_merge and actual:
                c.fail("Squash merges are allowed, but policy requires them to be disabled")

        # Check if rebase merges should be allowed
        allow_rebase_merge = variable_or_default("allow_rebase_merge", None)
        if allow_rebase_merge is not None:
            try:
                allow_rebase_merge = allow_rebase_merge.lower() in ['true', '1', 'yes']
            except (AttributeError, ValueError):
                raise ValueError(f"allow_rebase_merge must be a boolean, got: {allow_rebase_merge}")

            actual = merge_strategies.get_value_or_default(".allow_rebase_merge", False)
            if allow_rebase_merge and not actual:
                c.fail("Rebase merges are disabled, but policy requires them to be allowed")
            elif not allow_rebase_merge and actual:
                c.fail("Rebase merges are allowed, but policy requires them to be disabled")


if __name__ == "__main__":
    main()
