from lunar_policy import Check


def check_composer_json_exists(node=None):
    """Check that composer.json file exists in a PHP project."""
    c = Check("composer-json-exists", "Ensures composer.json exists", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")
        if not php.get_node(".project_exists").exists():
            c.skip("No PHP project detected in this component")

        composer = php.get_node(".composer")
        if not composer.exists():
            c.skip("Composer data not available - ensure php collector has run")

        json_exists = composer.get_node(".json_exists")
        if not json_exists.exists():
            c.skip("Composer data not available - ensure php collector has run")

        c.assert_true(
            json_exists.get_value(),
            "composer.json not found. Run 'composer init' to create one for dependency management."
        )
    return c


if __name__ == "__main__":
    check_composer_json_exists()
