from lunar_policy import Check

with Check("sca", "SCA scanner should be run on each code change") as c:
    # Only check on PRs, skip on main branch
    is_pr = c.get_node(".github.is_pr")
    if not is_pr.exists() or not is_pr.get_value_or_default(".", False):
        c.assert_true(True, "Skipped on main branch (only runs on PRs)")
    else:
        c.assert_true(c.exists(".sca.run"), (
            "SCA should be run in PRs. "
            "Configure either Snyk or Semgrep to scan your PRs, "
            "either via GitHub app or by running their CLI in your CI steps."
        ))
