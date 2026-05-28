from lunar_policy import Check


def main(node=None):
    c = Check(
        "submodules-no-floating-branches",
        "No submodule should declare a `branch` field tracking a floating ref",
        node=node,
    )
    with c:
        submodules = (
            c.get_node(".git.submodules").get_value_or_default(".", None)
        )
        if submodules is None:
            c.skip("No `.gitmodules` found — repo has no submodules")
            return c

        modules = submodules.get("modules") or []
        for module in modules:
            branch = (module.get("branch") or "").strip()
            if branch:
                name = module.get("name") or "<unknown>"
                c.fail(
                    f"Submodule '{name}' tracks branch '{branch}' — remove "
                    "the `branch` directive to keep the submodule pinned by "
                    "SHA"
                )
    return c


if __name__ == "__main__":
    main()
