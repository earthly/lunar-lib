from lunar_policy import Check


def main(node=None):
    c = Check(
        "signed-commits-recent",
        "Every recent commit on the default branch should carry a valid GPG/SSH signature",
        node=node,
    )
    with c:
        signing = (
            c.get_node(".git.signing").get_value_or_default(".", None)
        )
        if signing is None:
            c.fail(
                "No `.git.signing` data — the signed-commits sub-collector "
                "did not run (likely a shallow or empty clone). Ensure the "
                "git collector ran on a full history."
            )
            return c

        examined = signing.get("commits_examined") or 0
        counts = signing.get("signature_counts") or {}
        good = counts.get("good") or 0
        unsigned = counts.get("unsigned") or 0
        bad = counts.get("bad") or 0
        unknown = counts.get("unknown") or 0
        expired = counts.get("expired") or 0
        revoked = counts.get("revoked") or 0
        invalid = unsigned + bad + unknown + expired + revoked
        branch = signing.get("default_branch") or "<unknown>"

        if examined == 0:
            c.fail(
                f"No commits found on '{branch}' to inspect for signature "
                "status."
            )
            return c

        if invalid > 0:
            details = []
            if unsigned:
                details.append(f"{unsigned} unsigned")
            if bad:
                details.append(f"{bad} bad")
            if unknown:
                details.append(f"{unknown} unknown")
            if expired:
                details.append(f"{expired} expired")
            if revoked:
                details.append(f"{revoked} revoked")
            c.fail(
                f"{invalid} of {examined} recent commits on '{branch}' "
                f"are not validly signed ({', '.join(details)}). "
                "Configure GPG/SSH signing and require it via branch "
                "protection."
            )
    return c


if __name__ == "__main__":
    main()
