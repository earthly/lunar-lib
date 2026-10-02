# Category: `.vcs`

Version control settings (GitHub, GitLab, Bitbucket, etc.).

```json
{
  "vcs": {
    "provider": "github",
    "default_branch": "main",
    "branch_protection": {
      "enabled": true,
      "source": "ruleset",
      "branch": "main",
      "require_pr": true,
      "required_approvals": 2,
      "require_codeowner_review": true,
      "require_status_checks": true,
      "required_checks": ["ci/build", "ci/test"],
      "allow_force_push": false,
      "rulesets": [
        {
          "id": 1234567,
          "name": "main",
          "source_type": "Repository",
          "source": "acme/payments",
          "bypass_actors": [{"actor_type": "OrganizationAdmin", "bypass_mode": "always"}]
        }
      ]
    },
    "pr": {
      "number": 123,
      "title": "[ABC-456] Add payment validation",
      "description": "This PR adds validation logic for payment amounts...",
      "author": "jdoe",
      "labels": ["enhancement", "payments"],
      "head_sha": "9f1c2e7d...",
      "reviews": [
        {"reviewer": "alice", "state": "APPROVED", "submitted_at": "2024-05-02T15:40:51Z", "commit_sha": "9f1c2e7d..."}
      ],
      "commits": [
        {"sha": "9f1c2e7d...", "author": "jdoe", "signature": {"verified": true, "reason": "valid"}}
      ],
      "ticket": {
        "id": "ABC-456",
        "source": "jira",
        "url": "https://acme.atlassian.net/browse/ABC-456"
      }
    },
    "release_range": {
      "tag_pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$",
      "head_sha": "c3e8a1f6...",
      "default_branch": "main",
      "base": {"tag": "v2.3.0", "sha": "e1d4b7a0..."},
      "total_commits": 1,
      "truncated": false,
      "commits": [
        {
          "sha": "c3e8a1f6...",
          "author": "jdoe",
          "signature": {"verified": true, "reason": "valid"},
          "pull_request": {"number": 123, "base_branch": "main", "head_branch": "abc-456-payment-validation", "merged_at": "2024-05-02T16:02:13Z",
                           "merged_by": "jdoe", "head_sha": "9f1c2e7d...",
                           "approvals": [{"reviewer": "alice", "submitted_at": "2024-05-02T15:40:51Z", "commit_sha": "9f1c2e7d..."}]}
        }
      ]
    }
  }
}
```

**Note:** The `.vcs.pr` object is only present when in PR context. Check `c.exists(".vcs.pr")` before accessing. `.vcs.release_range` is only present on the default branch, and only when the github collector's opt-in `release-range` sub-collector is configured. A commit without a `pull_request` belongs to no merged PR. `pull_request.base_branch` / `head_branch` say where that PR merged from and into: a gitflow feature commit is linked only to its PR into `develop`, and reached the default branch through the later PR whose `head_branch` is `develop`.

A ruleset's `bypass_actors` is omitted when the collector's token can't see it (GitHub shows it only to callers with write access to the ruleset); `[]` means nobody can bypass.

## Key Policy Paths

- `.vcs.default_branch` — Default branch name
- `.vcs.branch_protection.enabled` — Protection active
- `.vcs.branch_protection.source` — How protection was detected: `"classic"` (legacy branch protection), `"ruleset"` (GitHub rulesets), or `"none"` (neither configured)
- `.vcs.branch_protection.required_approvals` — Min approvals
- `.vcs.branch_protection.require_codeowner_review` — CODEOWNER approval
- `.vcs.branch_protection.rulesets[].bypass_actors` — Who can bypass each ruleset (absent when not visible to the token)
- `.vcs.branch_protection.enforce_admins` — Classic protection applies to administrators
- `.vcs.pr.ticket.id` — Extracted ticket reference (only in PR context)
- `.vcs.pr.reviews[]` — Reviews submitted before the last push (only in PR context)
- `.vcs.pr.commits[].signature.verified` — GitHub verified the commit's signature (only in PR context)
- `.vcs.release_range.commits[].pull_request` — The merged PR that brought a released commit in (default branch only)
