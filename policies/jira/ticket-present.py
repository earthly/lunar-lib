from lunar_policy import Check
from helpers import is_pr_context


def main(node=None):
    c = Check("ticket-present", "PRs should reference a Jira ticket", node=node)
    with c:
        if not is_pr_context():
            c.skip("Not in a PR context")
            return c

        if not c.exists(".vcs.pr.ticket"):
            c.fail("PR does not reference a Jira ticket. "
                   "Include a ticket ID in the PR title (e.g. [ABC-123]).")
            return c

        ticket_id = c.get_value_or_default(".vcs.pr.ticket.id", "")
        if not ticket_id:
            c.fail("PR does not reference a Jira ticket. "
                   "Include a ticket ID in the PR title (e.g. [ABC-123]).")
    return c


if __name__ == "__main__":
    main()
