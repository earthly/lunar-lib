from lunar_policy import Check


def check_mix_project_exists(node=None):
    """Check that mix.exs exists in an Elixir project."""
    c = Check("mix-project-exists", "Ensures mix.exs exists", node=node)
    with c:
        elixir = c.get_node(".lang.elixir")
        if not elixir.exists():
            c.skip("Not an Elixir project")

        mix_exs = elixir.get_node(".mix_exs_exists")
        if not mix_exs.exists():
            c.skip("Mix data not available - ensure elixir collector has run")

        c.assert_true(
            mix_exs.get_value(),
            "mix.exs not found. Initialize with 'mix new <project-name>'."
        )
    return c


if __name__ == "__main__":
    check_mix_project_exists()
