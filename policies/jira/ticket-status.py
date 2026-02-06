from lunar_policy import Check, variable_or_default
from helpers import is_pr_context


def main(node=None):
    c = Check("ticket-status", "Jira ticket should be in an acceptable status", node=node)
    with c:
        if not is_pr_context():
            c.skip("Not in a PR context")
            return c

        if not c.exists(".jira.ticket"):
            c.skip("No Jira ticket data available")
            return c

        allowed_str = variable_or_default("allowed_statuses", "")
        disallowed_str = variable_or_default("disallowed_statuses", "")

        allowed = [s.strip() for s in allowed_str.split(",") if s.strip()]
        disallowed = [s.strip() for s in disallowed_str.split(",") if s.strip()]

        # If both lists are empty, nothing to check.
        if not allowed and not disallowed:
            return c

        status = c.get_value_or_default(".jira.ticket.status", "")
        ticket_key = c.get_value_or_default(".jira.ticket.key", "unknown")

        if not status:
            c.skip("Jira ticket has no status information")
            return c

        if allowed and status not in allowed:
            c.fail(f"Ticket {ticket_key} has status '{status}' which is not in "
                   f"the allowed list: {', '.join(allowed)}.")

        if disallowed and status in disallowed:
            c.fail(f"Ticket {ticket_key} has status '{status}' which is in "
                   f"the disallowed list: {', '.join(disallowed)}.")
    return c


if __name__ == "__main__":
    main()
