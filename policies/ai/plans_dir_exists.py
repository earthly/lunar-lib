from lunar_policy import Check


def main(node=None):
    c = Check("plans-dir-exists", "Dedicated plans directory should exist for AI agent task planning", node=node)
    with c:
        plans_dir = c.get_node(".ai.plans_dir")
        plans_data = plans_dir.get_value_or_default(".", None)
        if plans_data is None:
            c.fail(
                "No plans directory data found — ensure the ai collector is enabled. "
                "Exclude this policy if a plans directory is not required for this component."
            )
            return c

        exists = plans_dir.get_value_or_default(".exists", False)
        c.assert_true(
            exists,
            "No plans directory found (e.g. .agents/plans/). "
            "Create one to keep AI-generated plans organized and reviewable."
        )
    return c


if __name__ == "__main__":
    main()
