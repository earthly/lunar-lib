"""Check that Dockerfiles pass hadolint linting without issues above severity threshold."""

from lunar_policy import Check, variable_or_default


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2, "style": 3}


def main():
    with Check("dockerfile-lint-clean", "Dockerfiles should pass hadolint linting") as c:
        lint_results = c.get_node(".containers.lint_results")
        if not lint_results.exists():
            return

        threshold_name = variable_or_default("hadolint_severity", "error").lower()
        if threshold_name not in SEVERITY_ORDER:
            valid = ", ".join(SEVERITY_ORDER.keys())
            raise ValueError(
                f"Invalid hadolint_severity '{threshold_name}'. Valid values: {valid}"
            )
        threshold = SEVERITY_ORDER[threshold_name]

        for result in lint_results:
            path = result.get_value(".path")
            issues_node = result.get_node(".issues")

            if not issues_node.exists():
                continue

            issues = issues_node.get_value()
            violations = [
                i for i in issues
                if SEVERITY_ORDER.get(i.get("severity", "style"), 3) <= threshold
            ]

            if violations:
                rules = ", ".join(sorted(set(v["rule"] for v in violations)))
                c.fail(
                    f"'{path}' has {len(violations)} hadolint "
                    f"issue(s) at or above '{threshold_name}': {rules}"
                )


if __name__ == "__main__":
    main()
