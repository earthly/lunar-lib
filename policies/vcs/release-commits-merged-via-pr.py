from lunar_policy import Check

MAX_LISTED = 10


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
        total = rr.get_value_or_default(".total_commits", len(commits))
        truncated = rr.get_value_or_default(".truncated", False)

        missing = [commit for commit in commits if "pull_request" not in commit]
        if missing:
            checked = f" (checked {len(commits)} of {total})" if truncated else ""
            listed = "".join(
                f"\n    * {commit.get('sha', '')[:12]}" + (f" by {commit['author']}" if commit.get("author") else "")
                for commit in missing[:MAX_LISTED]
            )
            if len(missing) > MAX_LISTED:
                listed += f"\n    * +{len(missing) - MAX_LISTED} more (see .vcs.release_range)"
            c.fail(
                f"{len(missing)} commit(s) since {tag} did not reach the default branch "
                f"through a merged pull request{checked}:{listed}"
            )
        elif truncated:
            # The unchecked commits are unknown, not compliant: never pass on them.
            c.skip(
                f"Only the oldest {len(commits)} of {total} commits since {tag} were collected. "
                "Raise release_range_max_commits on the github collector to check the whole range."
            )
    return c


if __name__ == "__main__":
    main()
