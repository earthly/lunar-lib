import json

from lunar_policy import Check, variable_or_default

from min_java_version import compare_java_versions, omits_required_update, parse_java_version


def _problem(raw, minimum):
    """Return why one recorded CI version misses the minimum, or None if it meets it."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "No Java version recorded"
    try:
        actual = parse_java_version(raw)
    except ValueError as e:
        shown = f'"{raw}"' if isinstance(raw, str) else json.dumps(raw, default=str)
        return f"Java version {shown} {e}"
    if omits_required_update(actual, minimum):
        return (
            f"Java {actual.text} does not specify an update release, "
            f"so it cannot be shown to meet minimum {minimum.text}"
        )
    if compare_java_versions(actual, minimum) < 0:
        return f"Java {actual.text} is below minimum {minimum.text}"
    return None


def check_min_java_version_cicd(min_version=None, node=None):
    """Check that every Java version recorded in CI meets the minimum."""
    if min_version is None:
        min_version = variable_or_default("min_java_version_cicd", "17")

    c = Check("min-java-version-cicd", "Ensures CI/CD Java version meets minimum", node=node)
    with c:
        cmds_node = c.get_node(".lang.java.cicd.cmds")
        if not cmds_node.exists():
            c.skip("No java or javac commands recorded in CI")
        cmds = cmds_node.get_value()
        if not cmds:
            c.skip("No java or javac commands recorded in CI")

        try:
            minimum = parse_java_version(min_version)
        except ValueError as e:
            c.fail(f'min_java_version_cicd "{min_version}" {e}')
            return c

        # One finding per distinct problem, so a JDK that ran many commands is reported once.
        problems = {}
        for entry in cmds:
            entry = entry if isinstance(entry, dict) else {}
            problem = _problem(entry.get("version"), minimum)
            if problem:
                problems.setdefault(problem, []).append(entry.get("cmd") or "unknown command")

        c.assert_true(
            not problems,
            f"CI ran Java that does not meet minimum {minimum.text}",
        )
        for problem, commands in problems.items():
            count = f"{len(commands)} commands, e.g." if len(commands) > 1 else "command"
            c.fail(f"{problem} ({count} '{commands[0]}')")
    return c


if __name__ == "__main__":
    check_min_java_version_cicd()
