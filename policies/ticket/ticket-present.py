from lunar_policy import Check


def main(node=None):
    c = Check("ticket-present", "PRs should reference a Jira ticket", node=node)
    with c:
        if not c.exists(".vcs.pr.ticket"):
            c.fail("PR does not reference a Jira ticket. "
                   "Include a ticket ID in the PR title (e.g. [ABC-123]).")
            return c

        ticket_id = c.get_value_or_default(".vcs.pr.ticket.id", "")
        c.assert_true(bool(ticket_id),
                      "PR does not reference a Jira ticket. "
                      "Include a ticket ID in the PR title (e.g. [ABC-123]).")
    return c


if __name__ == "__main__":
    main()
