import json
import os

from lunar_policy import Check, variable_or_default


def check_executed(node=None, component_tags=None):
    """Check that tests were executed in CI.
    
    Args:
        node: Optional Node for testing. If None, loads from environment.
        component_tags: Optional list of component tags for testing.
    
    Returns:
        Check object with result.
    """
    c = Check("executed", "Ensures tests were executed in CI", node=node)
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
        
        c.assert_exists(
            ".testing",
            "No test execution data found. Ensure tests are configured to run in CI."
        )
    return c


if __name__ == "__main__":
    check_executed()
