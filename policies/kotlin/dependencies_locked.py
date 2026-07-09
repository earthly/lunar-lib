from lunar_policy import Check


def check_dependencies_locked(node=None):
    """Check that a dependency lockfile is committed for reproducible builds."""
    c = Check(
        "dependencies-locked",
        "Ensures gradle.lockfile is committed",
        node=node,
    )
    with c:
        kotlin = c.get_node(".lang.kotlin")
        if not kotlin.exists():
            c.skip("Not a Kotlin project")
        project_exists_node = kotlin.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Kotlin project detected in this component")

        lock_node = kotlin.get_node(".lockfile_exists")
        has_lock = lock_node.get_value() if lock_node.exists() else False

        c.assert_true(
            has_lock,
            "No dependency lockfile detected. Enable Gradle dependency locking "
            "(`dependencyLocking { lockAllConfigurations() }`), run "
            "`./gradlew dependencies --write-locks`, and commit gradle.lockfile "
            "for reproducible builds.",
        )
    return c


if __name__ == "__main__":
    check_dependencies_locked()
