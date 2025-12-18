import semver
from lunar_policy import Check, variable_or_default

with Check("java-version", "Uses Recent Java Version") as c:
    min_version = semver.VersionInfo.parse(variable_or_default("min_java_version", "17.0.0"))
    
    # Check version from code collector
    if c.exists(".lang.java.version"):
        version_str = c.get_value(".lang.java.version")
        if version_str:
            try:
                v = semver.VersionInfo.parse(version_str)
                c.assert_greater_or_equal(v, min_version, f"Java version {version_str} is below minimum required {min_version}")
            except ValueError:
                pass
    
    # Check versions from CI/CD commands
    cmds = c.get_node(".lang.java.native.java.cicd.cmds")
    if cmds.exists():
        for cmd in cmds:
            version_str = cmd.get_value_or_default(".version", "")
            if version_str:
                try:
                    v = semver.VersionInfo.parse(version_str)
                    cmd_str = cmd.get_value_or_default(".cmd", "<unknown>")
                    c.assert_greater_or_equal(v, min_version, f"Java command '{cmd_str}' uses version {version_str} which is below minimum required {min_version}")
                except ValueError:
                    pass

