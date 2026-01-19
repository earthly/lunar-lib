from lunar_policy import Check, variable_or_default


def main():
    with Check("allowed-merge-strategies", "Merge strategies should match allowed list") as c:
        allowed_merge_strategies = variable_or_default("allowed_merge_strategies", "")
        if not allowed_merge_strategies:
            c.skip("allowed_merge_strategies not configured")

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
            is_enabled = c.get_value(f".vcs.merge_strategies{json_path}")

            strategy_display = {
                "merge": "Merge commits",
                "squash": "Squash merges",
                "rebase": "Rebase merges"
            }[strategy_name]

            if is_allowed:
                c.assert_true(is_enabled, f"{strategy_display} are disabled, but policy allows them (should be enabled)")
            else:
                c.assert_false(is_enabled, f"{strategy_display} are enabled, but policy does not allow them (should be disabled)")


if __name__ == "__main__":
    main()
