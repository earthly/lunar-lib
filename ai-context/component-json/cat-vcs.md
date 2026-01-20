# Category: `.vcs`

Version control settings (GitHub, GitLab, Bitbucket, etc.).

```json
{
  "vcs": {
    "provider": "github",
    "default_branch": "main",
    "branch_protection": {
      "enabled": true,
      "branch": "main",
      "require_pr": true,
      "required_approvals": 2,
      "require_codeowner_review": true,
      "require_status_checks": true,
      "required_checks": ["ci/build", "ci/test"],
      "allow_force_push": false
    },
    "pr": {
      "number": 123,
      "title": "[ABC-456] Add payment validation",
      "description": "This PR adds validation logic for payment amounts...",
      "author": "jdoe",
      "labels": ["enhancement", "payments"],
      "reviewers": ["alice", "bob"],
      "approved": true,
      "commits": 3,
      "files_changed": 12,
      "ticket": {
        "id": "ABC-456",
        "source": "jira",
        "url": "https://acme.atlassian.net/browse/ABC-456"
      }
    }
  }
}
```

**Note:** The `.vcs.pr` object is only present when in PR context. Check `c.exists(".vcs.pr")` before accessing.

## Key Policy Paths

- `.vcs.default_branch` — Default branch name
- `.vcs.branch_protection.enabled` — Protection active
- `.vcs.branch_protection.required_approvals` — Min approvals
- `.vcs.branch_protection.require_codeowner_review` — CODEOWNER approval
- `.vcs.pr.ticket.id` — Extracted ticket reference (only in PR context)
- `.vcs.pr.approved` — PR has required approvals (only in PR context)
