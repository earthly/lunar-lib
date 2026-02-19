from lunar_policy import Check, variable_or_default


def check_vendoring(mode=None, node=None):
    """Check vendoring policy (required/forbidden/none)."""
    if mode is None:
        mode = variable_or_default("vendoring_mode", "none")

    c = Check("vendoring", "Enforces vendoring policy", node=node)
    with c:
        go = c.get_node(".lang.go")
        if not go.exists():
            c.skip("Not a Go project")

        if mode == "none":
            c.skip("Vendoring check disabled (vendoring_mode=none)")

        vendor_node = go.get_node(".vendor_exists")
        vendor_exists = vendor_node.get_value() if vendor_node.exists() else False

        if mode == "required":
            c.assert_true(
                vendor_exists,
                "Vendor directory required but not found. Run 'go mod vendor' to create it."
            )
        elif mode == "forbidden":
            c.assert_true(
                not vendor_exists,
                "Vendor directory found but vendoring is forbidden. Remove the vendor/ directory."
            )
        else:
            c.fail(f"Invalid vendoring_mode: '{mode}'. Use 'required', 'forbidden', or 'none'.")
    return c


if __name__ == "__main__":
    check_vendoring()
