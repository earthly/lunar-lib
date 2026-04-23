"""Ensure the SonarQube maintainability rating meets the configured minimum."""

from lunar_policy import Check, variable_or_default

RATING_ORDER = ["A", "B", "C", "D", "E"]


def main(node=None):
    c = Check("min-maintainability-rating", "SonarQube maintainability rating meets minimum", node=node)
    with c:
        min_rating = variable_or_default("min_maintainability_rating", "A").upper()
        if min_rating not in RATING_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_maintainability_rating' must be one of {RATING_ORDER}, got '{min_rating}'"
            )

        rating_node = c.get_node(".code_quality.native.sonarqube.ratings.maintainability")
        if not rating_node.exists():
            c.skip("No SonarQube maintainability rating available for this component")

        actual = rating_node.get_value()
        if actual not in RATING_ORDER:
            raise ValueError(
                f"SonarQube reported unexpected maintainability rating '{actual}'. Expected one of {RATING_ORDER}."
            )

        if RATING_ORDER.index(actual) > RATING_ORDER.index(min_rating):
            c.fail(
                f"SonarQube maintainability rating {actual} is worse than minimum {min_rating}"
            )
    return c


if __name__ == "__main__":
    main()
