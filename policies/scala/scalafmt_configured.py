from lunar_policy import Check


def check_scalafmt_configured(node=None):
    """Check that .scalafmt.conf is committed at the repo root."""
    c = Check(
        "scalafmt-configured",
        "Ensures .scalafmt.conf is committed",
        node=node,
    )
    with c:
        scala = c.get_node(".lang.scala")
        if not scala.exists():
            c.skip("Not a Scala project")

        fmt_node = scala.get_node(".scalafmt_configured")
        configured = fmt_node.get_value() if fmt_node.exists() else False

        c.assert_true(
            configured,
            ".scalafmt.conf not found. Add a .scalafmt.conf at the repo root "
            "to enforce consistent code formatting.",
        )
    return c


if __name__ == "__main__":
    check_scalafmt_configured()
