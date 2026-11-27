from lunar_policy import Check, variable_or_default

# Why the setting couldn't be read, by the gitlab collector's .error value.
UNKNOWN_CAUSES = {
    "forbidden": "GitLab denied the read (HTTP 403); it shows this setting only to project Maintainers",
    "not_found": "GitLab returned 404; the project is gone or the collector's token can't see it",
}


def main(node=None):
    c = Check(
        "require-job-token-allowlist",
        "GitLab project should limit which projects' CI/CD job tokens can access it",
        node=node,
    )
    with c:
        if variable_or_default("require_job_token_allowlist", "false").strip().lower() != "true":
            # Opt-in, so a whole-policy import, at any enforcement level, doesn't
            # start failing GitLab projects after an upgrade.
            c.skip('Not enabled. Set the `require_job_token_allowlist` input to "true" to check the CI/CD job token allowlist.')

        node = c.get_node(".vcs.job_token_allowlist")
        if not node.exists():
            # A GitLab-only setting, read on the default branch only. Absent also
            # covers a failed read (401, 429, 5xx, network): unknown, not a fail.
            c.skip("No job token allowlist data: the gitlab collector's job-token-allowlist sub-collector hasn't recorded this project.")

        data = node.get_value()
        if not isinstance(data, dict):
            c.skip("Job token allowlist status unknown: .vcs.job_token_allowlist is not an object.")

        # An unreadable setting is unknown: it must neither pass nor fail.
        error = data.get("error")
        if error is not None:
            cause = UNKNOWN_CAUSES.get(error, f"the collector recorded '{error}'")
            c.skip(f"Job token allowlist status unknown: {cause}.")

        enabled = data.get("enabled")
        if enabled is False:
            c.fail(
                "The CI/CD job token allowlist is off, so a job token from any project can access this one. "
                "In Settings > CI/CD > Job token permissions, select Only this project and any groups and projects in the allowlist."
            )
        elif enabled is not True:
            c.skip("Job token allowlist status unknown: .vcs.job_token_allowlist.enabled is not a boolean.")
    return c


if __name__ == "__main__":
    main()
