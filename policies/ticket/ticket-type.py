from lunar_policy import Check, variable_or_default

from helpers import ticket_path


def main(node=None):
    c = Check("ticket-type", "Ticket should be an acceptable issue type", node=node)
    with c:
        root = ticket_path()
        if not c.exists(f"{root}.type"):
            c.skip("No ticket type data available")

        allowed_str = variable_or_default("allowed_types", "")
        allowed = [t.strip() for t in allowed_str.split(",") if t.strip()]

        # If the allowed list is empty, any type is acceptable.
        if not allowed:
            c.skip("No type constraints configured")

        issue_type = c.get_value_or_default(f"{root}.type", "")
        ticket_id = c.get_value_or_default(f"{root}.id", "unknown")

        if not issue_type:
            c.skip("Ticket has no type information")

        c.assert_true(issue_type in allowed,
                      f"Ticket {ticket_id} has type '{issue_type}' which is not in "
                      f"the allowed list: {', '.join(allowed)}.")
    return c


if __name__ == "__main__":
    main()
