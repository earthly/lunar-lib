"""Verify the SonarQube quality gate is passing with no failed conditions."""

from lunar_policy import Check


def main(node=None):
    c = Check("quality-gate-passing", "SonarQube quality gate must be passing", node=node)
    with c:
        gate_node = c.get_node(".code_quality.native.sonarqube.quality_gate")
        if not gate_node.exists():
            c.skip("No SonarQube data available for this component")

        status_node = gate_node.get_node(".status")
        if not status_node.exists():
            c.fail(
                "SonarQube quality-gate status missing. Ensure the collector publishes .code_quality.native.sonarqube.quality_gate.status."
            )
            return c

        status = status_node.get_value()
        if status != "OK":
            failed_node = gate_node.get_node(".conditions_failed")
            failed = failed_node.get_value() if failed_node.exists() else "?"
            c.fail(
                f"SonarQube quality gate is {status} with {failed} failed condition(s)"
            )
            return c

        failed_node = gate_node.get_node(".conditions_failed")
        if failed_node.exists():
            failed_value = failed_node.get_value()
            c.assert_equals(
                failed_value,
                0,
                f"SonarQube quality gate reports {failed_value} failed condition(s) even though status is OK",
            )
    return c


if __name__ == "__main__":
    main()
