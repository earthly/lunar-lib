from lunar_policy import Check

with Check("jira-ticket-present", "Jira ticket must be present in PR") as c:
    is_pr = c.get_node(".github.is_pr")
    
    # Only check on PRs, skip on main branch
    if not is_pr.exists() or not is_pr.get_value_or_default(".", False):
        c.assert_true(True, "Skipped on main branch (only runs on PRs)")
    else:
        jira_ticket = c.get_node(".jira.ticket")
        if not jira_ticket.exists():
            c.fail("PRs should reference a Jira ticket")
