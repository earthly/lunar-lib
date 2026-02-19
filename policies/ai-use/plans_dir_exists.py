from lunar_policy import Check


def main(node=None):
    c = Check("plans-dir-exists", "Dedicated plans directory should exist for AI agent task planning", node=node)
    with c:
        plans_dir = c.get_node(".ai_use.plans_dir")
        exists = plans_dir.get_value(".exists") if plans_dir.exists() else False
        c.assert_true(
            exists,
            "No plans directory found (e.g. .agents/plans/). "
            "Create one to keep AI-generated plans organized and reviewable."
        )
    return c


if __name__ == "__main__":
    main()
