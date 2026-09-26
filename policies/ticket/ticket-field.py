from lunar_policy import Check, variable_or_default

from helpers import checked, field_values, is_empty, parse_list, ticket_path


def main(node=None):
    c = Check("ticket-field", "Ticket field should have an allowed value", node=node)
    with c:
        field = variable_or_default("ticket_field", "").strip().lstrip(".")
        if not field:
            c.skip("No ticket_field configured")

        allowed = parse_list("allowed_field_values",
                             variable_or_default("allowed_field_values", ""))
        root = ticket_path()
        sep = "" if field.startswith("[") else "."
        path = checked(f"{root}{sep}{field}")

        # A missing or unconfirmed ticket is ticket-present's and ticket-valid's
        # failure to report; failing here as well would only repeat it.
        if not c.exists(root):
            c.skip(f"No ticket data at {root}")
        ticket_id = c.get_value_or_default(f"{root}.id", "unknown")
        if c.get_value_or_default(f"{root}.valid", None) is not True:
            c.skip(f"Ticket {ticket_id} was not confirmed by the issue tracker")

        # The tracker's data is written in the same run as .valid, so a field
        # missing now is missing from the ticket, not still on its way.
        value = c.get_value_or_default(path, None)
        if is_empty(value):
            c.fail(f"Ticket {ticket_id} has no value for {field}.")
            return c

        if allowed:
            values = field_values(field, value)
            shown = ", ".join(f"'{v}'" for v in values)
            c.assert_true(any(v in allowed for v in values),
                          f"Ticket {ticket_id} field {field} is {shown}, which is "
                          f"not in the allowed list: {', '.join(allowed)}.")
    return c


if __name__ == "__main__":
    main()
