from lunar_policy import Check, variable_or_default
from helpers import is_pr_context


def main(node=None):
    c = Check("ticket-reuse", "Jira ticket should not be reused across too many PRs", node=node)
    with c:
        if not is_pr_context():
            c.skip("Not in a PR context")
            return c

        if not c.exists(".jira.ticket_reuse_count"):
            c.skip("No ticket reuse data available")
            return c

        max_reuse = int(variable_or_default("max_ticket_reuse", "3"))
        reuse_count = c.get_value(".jira.ticket_reuse_count")
        ticket_id = c.get_value_or_default(".vcs.pr.ticket.id",
                     c.get_value_or_default(".jira.ticket.key", "unknown"))

        c.assert_true(reuse_count <= max_reuse,
                      f"Ticket {ticket_id} has been used in {reuse_count} other PRs "
                      f"(max allowed: {max_reuse}). Create a new ticket for this work.")
    return c


if __name__ == "__main__":
    main()
