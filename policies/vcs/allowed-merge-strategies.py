from lunar_policy import Check, variable_or_default


def main(node=None, allowed_strategies_override=None):
    c = Check("allowed-merge-strategies", "Merge strategies should match allowed list", node=node)
    with c:
        c.assert_exists(".vcs.merge_strategies", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        allowed_merge_strategies = allowed_strategies_override if allowed_strategies_override is not None else variable_or_default("allowed_merge_strategies", "")
        allowed_list = [s.strip().lower() for s in allowed_merge_strategies.split(",") if s.strip()]

        # Validate configuration
        valid_strategies = {"merge", "squash", "rebase"}
        invalid = [s for s in allowed_list if s not in valid_strategies]

        if not allowed_list or invalid:
            if not allowed_list:
                error_msg = "allowed_merge_strategies must be configured. Provide a comma-separated list of allowed strategies (merge, squash, rebase)"
            else:
                error_msg = f"Invalid merge strategies: {', '.join(invalid)}. Valid options are: merge, squash, rebase"
            raise ValueError(f"Policy misconfiguration: {error_msg}")

        # Map strategy names to component JSON paths
        strategy_map = {
            "merge": ".allow_merge_commit",
            "squash": ".allow_squash_merge",
            "rebase": ".allow_rebase_merge"
        }

        # Check each strategy type - only fail if disallowed strategies are enabled
        for strategy_name, json_path in strategy_map.items():
            is_allowed = strategy_name in allowed_list
            is_enabled = c.get_value(f".vcs.merge_strategies{json_path}")

            # Only assert false for strategies not in the allowed list
            if not is_allowed:
                strategy_display = {
                    "merge": "Merge commits",
                    "squash": "Squash merges",
                    "rebase": "Rebase merges"
                }[strategy_name]

                c.assert_false(is_enabled, f"{strategy_display} are enabled, but policy does not allow them (should be disabled)")
    return c


if __name__ == "__main__":
    main()
