from lunar_policy import Check


def main(node=None):
    c = Check("plans-dir-exists", "Dedicated plans directory should exist for AI agent task planning", node=node)
    with c:
        exists = c.get_value(".ai_use.plans_dir.exists")
        c.assert_true(
            exists,
            "No plans directory found (e.g. .agents/plans/). "
            "Create one to keep AI-generated plans organized and reviewable."
        )
    return c


if __name__ == "__main__":
    main()
