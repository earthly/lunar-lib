import json
import os

from lunar_policy import Check, variable_or_default


def check_passing(node=None, component_tags=None):
    """Check that all tests pass.
    
    Skips if pass/fail data is not available (some collectors only 
    report execution, not results).
    
    Args:
        node: Optional Node for testing. If None, loads from environment.
        component_tags: Optional list of component tags for testing.
    
    Returns:
        Check object with result.
    """
    c = Check("passing", "Ensures all tests pass", node=node)
    with c:
        # Get required tags from input
        required_tags_str = variable_or_default("required_tags", "")
        required_tags = [t.strip() for t in required_tags_str.split(",") if t.strip()]
        
        # Get component tags
        if component_tags is None:
            component_tags = json.loads(os.environ.get("LUNAR_COMPONENT_TAGS", "[]"))
        
        # Skip if required_tags is set and component doesn't have any matching tags
        if required_tags and not any(tag in component_tags for tag in required_tags):
            c.skip(f"Component tags {component_tags} don't match required tags {required_tags}")
            return c
        
        # First check if we have test execution data at all
        if not c.exists(".testing"):
            c.skip("No test execution data found")
            return c

        # Check if pass/fail data is available
        if not c.exists(".testing.all_passing"):
            c.skip(
                "Test pass/fail data not available. "
                "This requires a collector that reports detailed test results."
            )
            return c

        # Assert tests are passing
        c.assert_true(
            c.get_value(".testing.all_passing"),
            "Tests are failing. Check CI logs for test failure details."
        )
    return c


if __name__ == "__main__":
    check_passing()
