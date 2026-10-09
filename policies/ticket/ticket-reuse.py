from lunar_policy import Check, variable_or_default

from helpers import ticket_path


def main(node=None):
    c = Check("ticket-reuse", "Ticket should not be reused across too many PRs", node=node)
    with c:
        root = ticket_path()
        if not c.exists(f"{root}.reuse_count"):
            c.skip("No ticket reuse data available")

        try:
            max_reuse = int(variable_or_default("max_ticket_reuse", "3"))
        except ValueError:
            c.skip("Invalid max_ticket_reuse configuration")

        reuse_count = c.get_value(f"{root}.reuse_count")
        ticket_id = c.get_value_or_default(f"{root}.id", "unknown")

        if not isinstance(reuse_count, (int, float)):
            c.skip("Ticket reuse count is not a number")

        c.assert_true(int(reuse_count) <= max_reuse,
                      f"Ticket {ticket_id} has been used in {reuse_count} other PRs "
                      f"(max allowed: {max_reuse}). Create a new ticket for this work.")
    return c


if __name__ == "__main__":
    main()
