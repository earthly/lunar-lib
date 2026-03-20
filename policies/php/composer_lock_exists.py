from lunar_policy import Check


def check_composer_lock_exists(node=None):
    """Check that composer.lock file exists in a PHP project."""
    c = Check("composer-lock-exists", "Ensures composer.lock exists", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")
        if not php.get_node(".project_exists").exists():
            c.skip("No PHP project detected in this component")

        composer = php.get_node(".composer")
        if not composer.exists():
            c.skip("Composer data not available - ensure php collector has run")

        lock_exists = composer.get_node(".lock_exists")
        if not lock_exists.exists():
            c.skip("Composer data not available - ensure php collector has run")

        c.assert_true(
            lock_exists.get_value(),
            "composer.lock not found. Run 'composer install' to generate a lockfile for reproducible builds."
        )
    return c


if __name__ == "__main__":
    check_composer_lock_exists()
