import os

from lunar_policy import Check

DEFAULT_SECRET_SCAN_HOOKS = (
    "gitleaks,detect-secrets,trufflehog,detect-aws-credentials,"
    "detect-private-key"
)


def _allowed_hook_ids():
    raw = os.environ.get("LUNAR_VAR_SECRET_SCAN_HOOK_IDS") or DEFAULT_SECRET_SCAN_HOOKS
    return {h.strip() for h in raw.split(",") if h.strip()}


def main(node=None):
    c = Check(
        "pre-commit-secret-scan-hook",
        "pre-commit config should include at least one secret-scanning hook",
        node=node,
    )
    with c:
        pre_commit = (
            c.get_node(".git.pre_commit").get_value_or_default(".", None)
        )
        if pre_commit is None:
            c.skip(
                "No pre-commit config found "
                "(pre-commit-config-exists covers this case)"
            )
            return c

        hook_ids = pre_commit.get("hook_ids") or []
        allowed = _allowed_hook_ids()
        matched = [h for h in hook_ids if h in allowed]
        if not matched:
            c.fail(
                "No secret-scanning hook configured. Add a hook from one of: "
                f"{', '.join(sorted(allowed))}."
            )
    return c


if __name__ == "__main__":
    main()
