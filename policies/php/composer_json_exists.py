from lunar_policy import Check


def check_composer_json_exists(node=None):
    """Check that composer.json file exists in a PHP project."""
    c = Check("composer-json-exists", "Ensures composer.json exists", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")

        composer_json = php.get_node(".composer_json_exists")
        if not composer_json.exists():
            c.skip("PHP project data not available - ensure php collector has run")

        c.assert_true(
            composer_json.get_value(),
            "composer.json not found. Initialize with 'composer init'"
        )
    return c


if __name__ == "__main__":
    check_composer_json_exists()
