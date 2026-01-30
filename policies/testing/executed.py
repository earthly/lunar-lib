from lunar_policy import Check


def check_executed(node=None):
    """Check that tests were executed in CI.
    
    Args:
        node: Optional Node for testing. If None, loads from environment.
    
    Returns:
        Check object with result.
    """
    c = Check("executed", "Ensures tests were executed in CI", node=node)
    with c:
        c.assert_exists(
            ".testing",
            "No test execution data found. Ensure tests are configured to run in CI."
        )
    return c


if __name__ == "__main__":
    check_executed()
