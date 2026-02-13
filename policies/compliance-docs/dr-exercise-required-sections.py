from lunar_policy import Check, variable_or_default


def main(node=None, required_sections_override=None, check_all_override=None):
    c = Check("dr-exercise-required-sections", "DR exercise records should contain required sections", node=node)
    with c:
        required_str = required_sections_override if required_sections_override is not None \
            else variable_or_default("exercise_required_sections", "")
        if not required_str:
            c.skip()

        required_sections = [s.strip() for s in required_str.split(",") if s.strip()]

        check_all_str = check_all_override if check_all_override is not None \
            else variable_or_default("exercises_check_all", "false")
        check_all = check_all_str.lower() == "true"

        dr = c.get_node(".oncall.disaster_recovery")
        c.assert_exists(".oncall.disaster_recovery",
            "DR data not found. Ensure the dr-docs collector is configured and has run.")

        exercises = dr.get_node(".exercises")
        if not exercises.exists() or dr.get_value_or_default(".exercise_count", 0) == 0:
            c.fail("No DR exercise records found — cannot verify sections")
            return c

        if check_all:
            for exercise in exercises:
                date = exercise.get_value_or_default(".date", "unknown")
                sections = exercise.get_value_or_default(".sections", [])
                sections_lower = [s.lower() for s in sections]
                missing = [s for s in required_sections if s.lower() not in sections_lower]
                if missing:
                    c.fail(f"DR exercise ({date}) is missing required sections: {', '.join(missing)}")
        else:
            latest = exercises.get_node("[0]")
            date = latest.get_value_or_default(".date", "unknown")
            sections = latest.get_value_or_default(".sections", [])
            sections_lower = [s.lower() for s in sections]
            missing = [s for s in required_sections if s.lower() not in sections_lower]
            if missing:
                c.fail(f"Latest DR exercise ({date}) is missing required sections: {', '.join(missing)}")
    return c


if __name__ == "__main__":
    main()
