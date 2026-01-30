from lunar_policy import Check, variable_or_default

with Check("vendoring", "Enforces vendoring policy") as c:
    mode = variable_or_default("vendoring_mode", "none")

    # Skip if not a Go project
    if not c.exists(".lang.go"):
        c.skip("Not a Go project")

    if mode == "none":
        c.skip("Vendoring check disabled (vendoring_mode=none)")

    vendor_exists = c.get_value_or_default(".lang.go.native.vendor.exists", False)

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
