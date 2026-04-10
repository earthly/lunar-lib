from lunar_policy import Check


def main(node=None):
    c = Check(
        "checkout-no-persist-credentials",
        "All checkout actions set persist-credentials: false",
        node=node,
    )
    with c:
        gha_node = c.get_node(".ci.native.github_actions")
        if not gha_node.exists():
            c.skip("No GitHub Actions data available")

        workflows_node = gha_node.get_node(".workflows")
        if not workflows_node.exists():
            c.skip("No workflow data available")

        workflows = workflows_node.get_value()
        if not isinstance(workflows, list):
            c.skip("Workflow data not in expected format")

        findings = []
        for wf in workflows:
            wf_file = wf.get("file", "<unknown>")
            jobs = wf.get("jobs", {})
            if not isinstance(jobs, dict):
                continue

            for job_name, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                for step in job.get("steps", []):
                    if not isinstance(step, dict):
                        continue
                    uses = step.get("uses", "")
                    if not isinstance(uses, str):
                        continue
                    if "actions/checkout" not in uses:
                        continue

                    # Check persist-credentials (default is true)
                    with_params = step.get("with", {})
                    persist = True
                    if isinstance(with_params, dict):
                        pc = with_params.get("persist-credentials")
                        if pc is False or (
                            isinstance(pc, str) and pc.lower() == "false"
                        ):
                            persist = False

                    if persist:
                        step_name = step.get("name", "<unnamed>")
                        findings.append(
                            f"{wf_file}: job '{job_name}', step "
                            f"'{step_name}' does not set "
                            f"persist-credentials: false"
                        )

        if findings:
            details = "; ".join(findings[:5])
            suffix = (
                f" (and {len(findings) - 5} more)" if len(findings) > 5 else ""
            )
            c.fail(
                f"{len(findings)} checkout step(s) with credential "
                f"persistence — {details}{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
