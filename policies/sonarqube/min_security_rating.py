"""Ensure the SonarQube security rating meets the configured minimum."""

from lunar_policy import Check, variable_or_default

RATING_ORDER = ["A", "B", "C", "D", "E"]


def main(node=None):
    c = Check("min-security-rating", "SonarQube security rating meets minimum", node=node)
    with c:
        min_rating = variable_or_default("min_security_rating", "A").upper()
        if min_rating not in RATING_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_security_rating' must be one of {RATING_ORDER}, got '{min_rating}'"
            )

        rating_node = c.get_node(".code_quality.native.sonarqube.ratings.security")
        if not rating_node.exists():
            c.skip("No SonarQube security rating available for this component")

        actual = rating_node.get_value()
        if actual not in RATING_ORDER:
            raise ValueError(
                f"SonarQube reported unexpected security rating '{actual}'. Expected one of {RATING_ORDER}."
            )

        if RATING_ORDER.index(actual) > RATING_ORDER.index(min_rating):
            c.fail(
                f"SonarQube security rating {actual} is worse than minimum {min_rating}"
            )
    return c


if __name__ == "__main__":
    main()
