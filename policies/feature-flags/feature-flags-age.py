from lunar_policy import Check, variable_or_default
import time


def main(node=None):
    """Check that feature flags are not older than the configured threshold."""
    c = Check("feature-flags-age", "Feature flags should not exceed age threshold", node=node)
    with c:
        # Get the maximum age threshold from configuration
        max_days_str = variable_or_default("max_days", "90")
        try:
            max_days = int(max_days_str)
        except ValueError:
            raise ValueError(
                f"Policy misconfiguration: 'max_days' must be an integer, got '{max_days_str}'"
            )

        # Get feature flags from the collected data
        feature_flags_node = c.get_node(".code_patterns.feature_flags")
        if not feature_flags_node.exists():
            # No feature flags found - check passes (nothing to validate)
            return c

        flags = feature_flags_node.get_value_or_default(".flags", [])
        if not flags or not isinstance(flags, list):
            # Empty or invalid data - check passes
            return c

        # Calculate the threshold timestamp (current time - max_days in seconds)
        current_time = int(time.time())
        seconds_per_day = 86400
        threshold_time = current_time - (max_days * seconds_per_day)

        # Check each feature flag for age violations
        for flag in flags:
            if not isinstance(flag, dict):
                continue

            name = flag.get("key", "<unknown>")
            created_at = flag.get("created_at")
            file_path = flag.get("file", "<unknown>")
            line = flag.get("line", "?")
            location = f"{file_path}:{line}"

            if created_at is None:
                continue

            # Check if the feature flag is older than the threshold
            if created_at < threshold_time:
                age_days = (current_time - created_at) // seconds_per_day
                c.assert_true(
                    False,
                    f"Feature flag '{name}' at {location} is {age_days} days old (max: {max_days} days)"
                )

    return c


if __name__ == "__main__":
    main()

