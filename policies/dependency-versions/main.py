import json, semver
from lunar_policy import Check, variable_or_default

with Check("dependency-version", "Checks for Dependencies with Vulnerable Versions") as c:
    language = variable_or_default("language", "")
    min_versions = json.loads(variable_or_default("min_versions", "{}"))
    
    deps = c.get_node(f".lang.{language}.dependencies.direct")
    if deps.exists():
        for dep in deps:
            dep_path = dep.get_value_or_default(".path", "")
            dep_version = dep.get_value_or_default(".version", "")
            if dep_path in min_versions and dep_version:
                v = semver.VersionInfo.parse(dep_version.lstrip('v'))
                min_v = semver.VersionInfo.parse(min_versions[dep_path].lstrip('v'))
                c.assert_greater_or_equal(v, min_v, f"'{dep_path}' version {dep_version} is below minimum safe version {min_versions[dep_path]}")
