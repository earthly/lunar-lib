from lunar_policy import Check

MAX_LISTED = 10
GITHUB_COMPARE_LIMIT = 1000


def prs_reaching(default, prs):
    """Numbers of the merged PRs that brought their commits into the default
    branch: those merged into it, and those merged into a branch that a PR
    merged at or after them then carried on toward it. Gitflow needs the second
    case: GitHub links a feature commit only to its PR into develop, not to the
    release PR from develop into main."""
    reached = {n for n, pr in prs.items() if pr.get("base_branch") == default}
    changed = True
    while changed:
        changed = False
        for n, pr in prs.items():
            if n in reached:
                continue
            for m in reached:
                carrier = prs[m]
                if (carrier.get("head_branch") == pr.get("base_branch")
                        and carrier.get("merged_at", "") >= pr.get("merged_at", "")):
                    reached.add(n)
                    changed = True
                    break
    return reached


def main(node=None):
    c = Check(
        "release-commits-merged-via-pr",
        "Every commit in a release should reach the default branch through a merged pull request",
        node=node,
    )
    with c:
        rr = c.get_node(".vcs.release_range")
        if not rr.exists():
            # The release-range sub-collector is opt-in; without it there is
            # no range to check.
            c.skip(
                "No release range collected. Set release_tag_pattern on the github "
                "collector to enable its release-range sub-collector."
            )

        if not rr.get_node(".base").exists():
            # The first release has no previous tag, so its range is the whole
            # history, including commits made before any pull request existed.
            pattern = rr.get_value_or_default(".tag_pattern", "")
            c.skip(f"No release tag matching '{pattern}' precedes this commit, so there is no range to check.")

        tag = rr.get_value_or_default(".base.tag", "the previous release")
        commits = rr.get_value_or_default(".commits", [])
        default = rr.get_value_or_default(".default_branch", "")
        if not commits or not default:
            c.skip(f"The release range since {tag} was recorded without its commits or default branch.")

        total = rr.get_value_or_default(".total_commits", len(commits))
        truncated = rr.get_value_or_default(".truncated", False)

        prs = {}
        for commit in commits:
            pr = commit.get("pull_request")
            if isinstance(pr, dict) and "number" in pr:
                prs.setdefault(pr["number"], pr)
        reached = prs_reaching(default, prs)

        violations = []
        for commit in commits:
            who = commit.get("sha", "")[:12] + (f" by {commit['author']}" if commit.get("author") else "")
            pr = commit.get("pull_request")
            if not isinstance(pr, dict):
                violations.append(f"{who}: no merged pull request")
            elif pr.get("number") not in reached and not truncated:
                # When truncated, the PR that carried it on may be among the
                # unrecorded commits, so it's unknown rather than a violation.
                violations.append(
                    f"{who}: merged into {pr.get('base_branch')} by #{pr.get('number')}, "
                    f"which no later pull request carried into {default}"
                )

        if violations:
            checked = f" (checked {len(commits)} of {total})" if truncated else ""
            listed = "".join(f"\n    * {v}" for v in violations[:MAX_LISTED])
            if len(violations) > MAX_LISTED:
                listed += f"\n    * +{len(violations) - MAX_LISTED} more (see .vcs.release_range)"
            c.fail(
                f"{len(violations)} commit(s) since {tag} did not reach {default} "
                f"through a merged pull request{checked}:{listed}"
            )
        elif truncated:
            # The unchecked commits are unknown, not compliant: never pass on them.
            if total > GITHUB_COMPARE_LIMIT:
                fix = (f"GitHub lists at most {GITHUB_COMPARE_LIMIT} commits of a comparison, "
                       "so a range this long can't be checked in full; release more often.")
            else:
                fix = "Raise release_range_max_commits on the github collector to check the whole range."
            c.skip(f"Only {len(commits)} of {total} commits since {tag} were recorded. {fix}")
    return c


if __name__ == "__main__":
    main()
