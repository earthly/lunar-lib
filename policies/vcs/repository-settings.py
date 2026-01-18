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

        # Check allowed merge strategies
        allowed_merge_strategies = variable_or_default("allowed_merge_strategies", None)
        if allowed_merge_strategies is not None:
            # Parse comma-separated list
            allowed_list = [s.strip().lower() for s in allowed_merge_strategies.split(",") if s.strip()]

            # Validate the list contains valid strategies
            valid_strategies = {"merge", "squash", "rebase"}
            invalid = [s for s in allowed_list if s not in valid_strategies]
            if invalid:
                raise ValueError(
                    f"Policy misconfiguration: Invalid merge strategies: {', '.join(invalid)}. "
                    f"Valid options are: merge, squash, rebase"
                )

            # Map strategy names to component JSON paths
            strategy_map = {
                "merge": ".allow_merge_commit",
                "squash": ".allow_squash_merge",
                "rebase": ".allow_rebase_merge"
            }

            # Check each strategy type
            for strategy_name, json_path in strategy_map.items():
                is_allowed = strategy_name in allowed_list
                is_enabled = merge_strategies.get_value_or_default(json_path, False)

                strategy_display = {
                    "merge": "Merge commits",
                    "squash": "Squash merges",
                    "rebase": "Rebase merges"
                }[strategy_name]

                if is_allowed and not is_enabled:
                    c.fail(f"{strategy_display} are disabled, but policy allows them (should be enabled)")
                elif not is_allowed and is_enabled:
                    c.fail(f"{strategy_display} are enabled, but policy does not allow them (should be disabled)")


if __name__ == "__main__":
    main()
