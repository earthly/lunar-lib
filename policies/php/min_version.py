"""Check that the composer.json PHP constraint meets the minimum for its release line."""
import re

from lunar_policy import Check, variable_or_default

from version_minimum import Runtime, compare_versions, parse_minimum

# A PHP release line is major.minor: 8.2, 8.3. A minimum may keep a
# Composer-style operator: ^8.1, ~8.1 and >=8.1 all mean 8.1.
PHP = Runtime(
    "PHP",
    line_length=2,
    forms="8.3, 8.3.14 or 8.4.0RC1",
    normalize=lambda text: re.sub(r"^(?:\^|~|>=?|=)\s*", "", text),
)


def lowest_allowed(constraint):
    """The lowest version a composer.json PHP constraint allows, or None.

    Takes the first version in each || alternative: ^8.1, ~8.1.0, >=8.1 <9.0
    and 8.1.* all allow 8.1, and ^7.4 || ^8.1 allows 7.4.
    """
    lowest = None
    for part in str(constraint).split("||"):
        m = re.search(r"\d+(?:\.\d+)*", part)
        if m:
            version = PHP.parse(m.group(0))
            if lowest is None or compare_versions(version, lowest) < 0:
                lowest = version
    return lowest


def check_min_version(min_version=None, node=None):
    """Check that PHP version constraint meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_version", "8.1")

    c = Check("min-version", "Ensures PHP version meets minimum", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")
        project_exists_node = php.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No PHP project detected in this component")

        version_node = php.get_node(".version")
        if not version_node.exists():
            c.skip("PHP version constraint not detected")

        constraint = version_node.get_value()
        if not constraint:
            c.skip("PHP version constraint is empty")

        try:
            minimum = parse_minimum(min_version, PHP)
        except ValueError as e:
            c.fail(f"min_version {e}")
            return c

        lowest = lowest_allowed(constraint)
        if lowest is None:
            c.fail(f"Could not parse PHP version constraint: {constraint}")
            return c

        floor, unlisted = minimum.match(lowest)
        if unlisted:
            c.fail(
                f"PHP version {constraint} (min {lowest.text}) is on release line "
                f"{minimum.line_text(lowest)}, which has no listed minimum ({minimum.text})."
            )
            return c
        below = floor is not None and compare_versions(lowest, floor) < 0
        c.assert_true(
            not below,
            f"PHP version {constraint} (min {lowest.text}) is below minimum {floor.text}. "
            "Update the PHP constraint in composer.json." if below else "",
        )
    return c


if __name__ == "__main__":
    check_min_version()
