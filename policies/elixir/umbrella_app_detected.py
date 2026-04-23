from lunar_policy import Check


def check_umbrella_app_detected(node=None):
    """Report whether the project is an umbrella app. Informational only."""
    c = Check(
        "umbrella-app-detected",
        "Reports whether the project is an umbrella application",
        node=node,
    )
    with c:
        elixir = c.get_node(".lang.elixir")
        if not elixir.exists():
            c.skip("Not an Elixir project")

        umbrella_node = elixir.get_node(".umbrella")
        if not umbrella_node.exists():
            c.skip("Umbrella data not available - ensure elixir collector has run")

        # Always passes — this check surfaces umbrella layout without gating.
        # The Component JSON carries the structural detail (apps list).
        c.assert_true(
            True,
            "Umbrella layout check"
        )
    return c


if __name__ == "__main__":
    check_umbrella_app_detected()
