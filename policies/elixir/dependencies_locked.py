from lunar_policy import Check


def check_dependencies_locked(node=None):
    """Check that mix.lock is committed for reproducible builds."""
    c = Check(
        "dependencies-locked",
        "Ensures mix.lock is committed for reproducible Hex dependency resolution",
        node=node,
    )
    with c:
        elixir = c.get_node(".lang.elixir")
        if not elixir.exists():
            c.skip("Not an Elixir project")

        lock_node = elixir.get_node(".mix_lock_exists")
        has_lock = lock_node.get_value() if lock_node.exists() else False

        c.assert_true(
            has_lock,
            "mix.lock not found. Run 'mix deps.get' and commit mix.lock for reproducible builds."
        )
    return c


if __name__ == "__main__":
    check_dependencies_locked()
