from lunar_policy import Check


def check_dependencies_locked(node=None):
    """Check that a dependency lockfile is committed for reproducible builds."""
    c = Check(
        "dependencies-locked",
        "Ensures build.sbt.lock or equivalent is committed",
        node=node,
    )
    with c:
        scala = c.get_node(".lang.scala")
        if not scala.exists():
            c.skip("Not a Scala project")

        lock_node = scala.get_node(".lockfile_exists")
        has_lock = lock_node.get_value() if lock_node.exists() else False

        c.assert_true(
            has_lock,
            "No dependency lockfile detected. For sbt, add the sbt-lock plugin "
            "(github.com/tkawachi/sbt-lock) and commit build.sbt.lock for "
            "reproducible builds.",
        )
    return c


if __name__ == "__main__":
    check_dependencies_locked()
