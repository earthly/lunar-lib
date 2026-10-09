from lunar_policy import Check

from helpers import missing_ticket_message, ticket_path


def main(node=None):
    c = Check("ticket-present", "PRs should reference a ticket", node=node)
    with c:
        root = ticket_path()
        if not c.exists(root):
            c.fail(missing_ticket_message(root))
            return c

        ticket_id = c.get_value_or_default(f"{root}.id", "")
        c.assert_true(bool(ticket_id), missing_ticket_message(root))
    return c


if __name__ == "__main__":
    main()
