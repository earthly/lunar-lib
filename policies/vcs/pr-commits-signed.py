from lunar_policy import Check

MAX_LISTED = 10


def main(node=None):
    c = Check("pr-commits-signed", "Every commit in a pull request should carry a verified signature", node=node)
    with c:
        if not c.get_node(".vcs.pr").exists():
            c.skip("No pull request data collected.")

        commits_node = c.get_node(".vcs.pr.commits")
        if not commits_node.exists():
            # Not collected (a non-GitHub collector, a PR over GitHub's 250-commit
            # listing limit, or an API error): unknown, so never pass on it.
            c.skip("No commit signature data collected; the github collector's pull-request sub-collector provides it.")

        commits = commits_node.get_value()
        unverified = [
            commit for commit in commits
            if not isinstance(commit.get("signature"), dict) or commit["signature"].get("verified") is not True
        ]
        if unverified:
            listed = "".join(
                f"\n    * {commit.get('sha', '')[:12]} ({(commit.get('signature') or {}).get('reason', 'no verification data')})"
                for commit in unverified[:MAX_LISTED]
            )
            if len(unverified) > MAX_LISTED:
                listed += f"\n    * +{len(unverified) - MAX_LISTED} more (see .vcs.pr.commits)"
            c.fail(f"{len(unverified)} of {len(commits)} commit(s) have no verified signature:{listed}")
    return c


if __name__ == "__main__":
    main()
