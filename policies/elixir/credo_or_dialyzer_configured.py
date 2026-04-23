from lunar_policy import Check


def _dialyzer_in_ci(elixir_node) -> bool:
    """Return True if `mix dialyzer` was observed in CI commands."""
    cmds_node = elixir_node.get_node(".cicd.cmds")
    if not cmds_node.exists():
        return False
    cmds = cmds_node.get_value() or []
    for entry in cmds:
        cmd = (entry or {}).get("cmd", "")
        if "dialyzer" in cmd:
            return True
    return False


def check_credo_or_dialyzer_configured(node=None):
    """Check that Credo or Dialyzer is configured for static analysis."""
    c = Check(
        "credo-or-dialyzer-configured",
        "Ensures Credo or Dialyzer is configured for static analysis",
        node=node,
    )
    with c:
        elixir = c.get_node(".lang.elixir")
        if not elixir.exists():
            c.skip("Not an Elixir project")

        credo_node = elixir.get_node(".credo_configured")
        dialyzer_node = elixir.get_node(".dialyzer_configured")

        credo = credo_node.get_value() if credo_node.exists() else False
        dialyzer = dialyzer_node.get_value() if dialyzer_node.exists() else False
        dialyzer_ci = _dialyzer_in_ci(elixir)

        c.assert_true(
            credo or dialyzer or dialyzer_ci,
            "Neither Credo (.credo.exs) nor Dialyzer detected. "
            "Add {:credo, ...} or {:dialyxir, ...} to deps for static analysis."
        )
    return c


if __name__ == "__main__":
    check_credo_or_dialyzer_configured()
