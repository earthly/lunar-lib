from lunar_policy import Check, variable_or_default
from helpers import is_pr_context


def main(node=None):
    c = Check("ticket-type", "Jira ticket should be an acceptable issue type", node=node)
    with c:
        if not is_pr_context():
            c.skip("Not in a PR context")

        if not c.exists(".jira.ticket"):
            c.skip("No Jira ticket data available")

        allowed_str = variable_or_default("allowed_types", "")
        allowed = [t.strip() for t in allowed_str.split(",") if t.strip()]

        # If the allowed list is empty, any type is acceptable.
        if not allowed:
            c.skip("No type constraints configured")

        issue_type = c.get_value_or_default(".jira.ticket.type", "")
        ticket_key = c.get_value_or_default(".jira.ticket.key", "unknown")

        if not issue_type:
            c.skip("Jira ticket has no type information")

        c.assert_true(issue_type in allowed,
                      f"Ticket {ticket_key} has type '{issue_type}' which is not in "
                      f"the allowed list: {', '.join(allowed)}.")
    return c


if __name__ == "__main__":
    main()
