from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("ticket-reuse", "Ticket should not be reused across too many PRs", node=node)
    with c:
        if not c.exists(".vcs.pr.ticket.reuse_count"):
            c.skip("No ticket reuse data available")

        try:
            max_reuse = int(variable_or_default("max_ticket_reuse", "3"))
        except ValueError:
            c.skip("Invalid max_ticket_reuse configuration")

        reuse_count = c.get_value(".vcs.pr.ticket.reuse_count")
        ticket_id = c.get_value_or_default(".vcs.pr.ticket.id", "unknown")

        if not isinstance(reuse_count, (int, float)):
            c.skip("Ticket reuse count is not a number")

        c.assert_true(int(reuse_count) <= max_reuse,
                      f"Ticket {ticket_id} has been used in {reuse_count} other PRs "
                      f"(max allowed: {max_reuse}). Create a new ticket for this work.")
    return c


if __name__ == "__main__":
    main()
