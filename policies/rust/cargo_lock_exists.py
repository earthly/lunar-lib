from lunar_policy import Check, variable_or_default


def check_cargo_lock_exists(lock_mode=None, node=None):
    """Check that Cargo.lock exists, with auto-detection for libs vs apps."""
    if lock_mode is None:
        lock_mode = variable_or_default("lock_mode", "auto")

    c = Check("cargo-lock-exists", "Ensures Cargo.lock exists for applications", node=node)
    with c:
        rust = c.get_node(".lang.rust")
        if not rust.exists():
            c.skip("Not a Rust project")

        if lock_mode == "none":
            c.skip("Cargo.lock check disabled (lock_mode=none)")

        has_lock_node = rust.get_node(".cargo_lock_exists")
        has_lock = has_lock_node.get_value() if has_lock_node.exists() else False

        if lock_mode == "auto":
            is_app_node = rust.get_node(".is_application")
            is_lib_node = rust.get_node(".is_library")
            is_app = is_app_node.get_value() if is_app_node.exists() else False
            is_lib = is_lib_node.get_value() if is_lib_node.exists() else False

            if is_lib and not is_app:
                c.skip("Cargo.lock not required for library crates")

            c.assert_true(
                has_lock,
                "Cargo.lock not found. Applications should commit Cargo.lock "
                "for reproducible builds. Run 'cargo generate-lockfile' to create it."
            )
        elif lock_mode == "required":
            c.assert_true(
                has_lock,
                "Cargo.lock not found. Run 'cargo generate-lockfile' to create it."
            )
        elif lock_mode == "forbidden":
            c.assert_true(
                not has_lock,
                "Cargo.lock should not be committed. Remove it from version control."
            )
        else:
            c.fail(f"Invalid lock_mode: '{lock_mode}'. Use 'auto', 'required', 'forbidden', or 'none'.")
    return c


if __name__ == "__main__":
    check_cargo_lock_exists()
