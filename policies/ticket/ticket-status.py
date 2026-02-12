from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("ticket-status", "Ticket should be in an acceptable status", node=node)
    with c:
        if not c.exists(".vcs.pr.ticket.status"):
            c.skip("No ticket status data available")

        allowed_str = variable_or_default("allowed_statuses", "")
        disallowed_str = variable_or_default("disallowed_statuses", "")

        allowed = [s.strip() for s in allowed_str.split(",") if s.strip()]
        disallowed = [s.strip() for s in disallowed_str.split(",") if s.strip()]

        # If both lists are empty, nothing to check.
        if not allowed and not disallowed:
            c.skip("No status constraints configured")

        status = c.get_value_or_default(".vcs.pr.ticket.status", "")
        ticket_id = c.get_value_or_default(".vcs.pr.ticket.id", "unknown")

        if not status:
            c.skip("Ticket has no status information")

        if allowed and status not in allowed:
            c.fail(f"Ticket {ticket_id} has status '{status}' which is not in "
                   f"the allowed list: {', '.join(allowed)}.")
        elif disallowed and status in disallowed:
            c.fail(f"Ticket {ticket_id} has status '{status}' which is in "
                   f"the disallowed list: {', '.join(disallowed)}.")
        else:
            c.assert_true(True, "")
    return c


if __name__ == "__main__":
    main()
