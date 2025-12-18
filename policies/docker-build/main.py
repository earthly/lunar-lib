from lunar_policy import Check

with Check("docker-build-git-sha", "Docker builds must include git SHA label") as c:
    builds = c.get_node(".docker_build.builds")
    if builds.exists():
        for build in builds:
            cmd = build.get_value_or_default(".cmd", "<unknown>")
            has_git_sha_label = build.get_value_or_default(".has_git_sha_label", False)
            c.assert_true(
                has_git_sha_label,
                f"Docker build command '{cmd}' does not include git_sha label"
            )
    else:
        c.assert_true(True, "No docker builds found")