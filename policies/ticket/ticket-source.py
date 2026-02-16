from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("ticket-source", "Ticket should come from an approved issue tracker", node=node)
    with c:
        if not c.exists(".vcs.pr.ticket.source"):
            c.skip("No ticket source data available")

        allowed_str = variable_or_default("allowed_sources", "")
        allowed = [s.strip().lower() for s in allowed_str.split(",") if s.strip()]

        if not allowed:
            c.skip("No source constraints configured")

        source = c.get_value_or_default(".vcs.pr.ticket.source.tool",
                  c.get_value_or_default(".vcs.pr.ticket.source", ""))
        ticket_id = c.get_value_or_default(".vcs.pr.ticket.id", "unknown")

        if not source:
            c.skip("Ticket has no source information")

        source_name = source if isinstance(source, str) else str(source)
        c.assert_true(source_name.lower() in allowed,
                      f"Ticket {ticket_id} comes from '{source_name}' which is not in "
                      f"the allowed list: {', '.join(allowed)}.")
    return c


if __name__ == "__main__":
    main()
