from lunar_policy import Check

from helpers import ticket_path


def main(node=None):
    c = Check("ticket-valid", "Referenced Jira ticket should be valid", node=node)
    with c:
        root = ticket_path()
        if not c.exists(root):
            c.skip("No ticket referenced in PR")

        ticket_id = c.get_value_or_default(f"{root}.id", "")
        if not ticket_id:
            c.skip("No ticket ID found")

        valid = c.get_value_or_default(f"{root}.valid", None)
        if valid is None:
            # tracker_error says why the collector could not confirm the
            # ticket. Trackers that do not report one leave it unset.
            tracker_error = c.get_value_or_default(f"{root}.tracker_error", None)
            if tracker_error == "not_found":
                c.fail(f"Ticket {ticket_id} does not exist in Jira.")
            elif tracker_error == "unreachable":
                c.fail(f"Ticket {ticket_id} could not be validated: Jira was unreachable.")
            else:
                c.fail(f"Ticket {ticket_id} could not be validated against Jira. "
                       "The ticket may not exist or the Jira API may be unreachable.")
            return c

        c.assert_true(valid, f"Ticket {ticket_id} is not valid in Jira.")
    return c


if __name__ == "__main__":
    main()
