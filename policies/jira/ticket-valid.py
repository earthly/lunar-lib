from lunar_policy import Check
from helpers import is_pr_context


def main(node=None):
    c = Check("ticket-valid", "Referenced Jira ticket should be valid", node=node)
    with c:
        if not is_pr_context():
            c.skip("Not in a PR context")
            return c

        if not c.exists(".vcs.pr.ticket"):
            c.skip("No ticket referenced in PR")
            return c

        ticket_id = c.get_value_or_default(".vcs.pr.ticket.id", "")
        if not ticket_id:
            c.skip("No ticket ID found")
            return c

        valid = c.get_value_or_default(".vcs.pr.ticket.valid", None)
        if valid is None:
            c.fail(f"Ticket {ticket_id} could not be validated against Jira. "
                   "The ticket may not exist or the Jira API may be unreachable.")
            return c

        c.assert_true(valid, f"Ticket {ticket_id} is not valid in Jira.")
    return c


if __name__ == "__main__":
    main()
