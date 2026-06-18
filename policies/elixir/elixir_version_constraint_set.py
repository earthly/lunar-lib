from lunar_policy import Check


def check_elixir_version_constraint_set(node=None):
    """Check that mix.exs declares an Elixir version requirement."""
    c = Check(
        "elixir-version-constraint-set",
        "Ensures mix.exs sets an `elixir:` version requirement",
        node=node,
    )
    with c:
        elixir = c.get_node(".lang.elixir")
        if not elixir.exists():
            c.skip("Not an Elixir project")
        project_exists_node = elixir.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Elixir project detected in this component")

        req_node = elixir.get_node(".elixir_requirement")
        req = req_node.get_value() if req_node.exists() else ""

        c.assert_true(
            bool(req),
            "Elixir version requirement missing in mix.exs. "
            "Add 'elixir: \"~> 1.15\"' (or desired minimum) to the project/0 block."
        )
    return c


if __name__ == "__main__":
    check_elixir_version_constraint_set()
