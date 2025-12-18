import semver
from lunar_policy import Check, variable_or_default

with Check("go-version", "Uses Recent Go Version in CI/CD") as c:
    cmds = c.get_node(".lang.go.cicd.cmds")

    if cmds.exists():
        min_version = semver.VersionInfo.parse(variable_or_default("min_version", "0.0.0"))
        for cmd in cmds:
            version_str = cmd.get_value_or_default(".version", "")
            if version_str:
                try:
                    v = semver.VersionInfo.parse(version_str)
                    cmd_str = cmd.get_value_or_default(".cmd", "<unknown>")
                    c.assert_greater_or_equal(
                        v, 
                        min_version, 
                        f"Go command '{cmd_str}' uses version {version_str} which is below minimum required {min_version}"
                    )
                except ValueError:
                    # Skip invalid version strings
                    pass
    else:
        c.assert_true(True, "No Go commands found in CI/CD")
