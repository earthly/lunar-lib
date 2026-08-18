"""Check that Dockerfiles pass hadolint linting without issues above severity threshold."""

from lunar_policy import Check, variable_or_default


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2, "style": 3}


def main(node=None):
    c = Check(
        "dockerfile-lint-clean",
        "Dockerfiles should pass hadolint linting",
        node=node,
    )
    with c:
        lint_results = c.get_node(".containers.lint_results")
        if not lint_results.exists():
            # Two different reasons lint_results can be absent, and the skip
            # reason has to name the right one. Normally it means the component
            # has no Dockerfiles, so the hadolint sub-collector wrote nothing.
            # But hadolint exiting unexpectedly also leaves lint_results unset —
            # it records the failure under .native.hadolint.error instead. Skip
            # either way (a broken tool shouldn't false-fail the component), but
            # don't claim "no Dockerfiles" when there are Dockerfiles.
            #
            # An *empty* array is a third, distinct signal — hadolint ran and
            # found no issues — and falls through to a genuine pass below.
            error = c.get_value_or_default(".containers.native.hadolint.error", None)
            if error is not None:
                c.skip(f"hadolint did not produce lint results: {error}")
            else:
                c.skip("No Dockerfiles found in this component")
            return c

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
    return c


if __name__ == "__main__":
    main()
