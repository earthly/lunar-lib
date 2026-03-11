from lunar_policy import Check


def check_composer_lock_exists(node=None):
    """Check that composer.lock file exists for reproducible builds."""
    c = Check("composer-lock-exists", "Ensures composer.lock exists", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")

        composer_lock = php.get_node(".composer_lock_exists")
        if not composer_lock.exists():
            c.skip("PHP project data not available - ensure php collector has run")

        c.assert_true(
            composer_lock.get_value(),
            "composer.lock not found. Run 'composer install' or 'composer update' "
            "to generate it and commit it to version control."
        )
    return c


if __name__ == "__main__":
    check_composer_lock_exists()
