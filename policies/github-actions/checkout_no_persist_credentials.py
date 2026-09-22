from lunar_policy import Check, variable_or_default

from exemptions import (
    find_exemption,
    format_exemptions,
    parse_exempt_jobs,
    stale_exemptions,
)


def main(node=None):
    c = Check(
        "checkout-no-persist-credentials",
        "All checkout actions set persist-credentials: false",
        node=node,
    )
    with c:
        # Parsed before any data is read: a malformed list must fail the check
        # rather than exempt anything.
        exemptions = parse_exempt_jobs(variable_or_default("exempt_jobs", ""))

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
        exempted = []
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

                    if not persist:
                        continue

                    exemption = find_exemption(exemptions, wf_file, job_name)
                    if exemption:
                        exempted.append(exemption)
                        continue

                    step_name = step.get("name", "<unnamed>")
                    findings.append(
                        f"{wf_file}: job '{job_name}', step "
                        f"'{step_name}' does not set "
                        f"persist-credentials: false"
                    )

        stale = stale_exemptions(exemptions, workflows)
        if stale:
            c.fail(
                f"{len(stale)} exempt_jobs entr"
                f"{'y names a job' if len(stale) == 1 else 'ies name jobs'} "
                f"the workflow does not define — {format_exemptions(stale)}"
            )

        if findings:
            details = "; ".join(findings[:5])
            suffix = (
                f" (and {len(findings) - 5} more)" if len(findings) > 5 else ""
            )
            exempt_suffix = (
                f" [{len(exempted)} exempted: {format_exemptions(exempted)}]"
                if exempted
                else ""
            )
            c.fail(
                f"{len(findings)} checkout step(s) with credential "
                f"persistence — {details}{suffix}{exempt_suffix}"
            )
        elif exempted and not stale:
            # skip() clears every earlier result, so this must stay behind both
            # failure paths — a stale entry has to survive into the result.
            c.skip(
                f"{len(exempted)} checkout step(s) with credential "
                f"persistence, all exempted — {format_exemptions(exempted)}"
            )

    return c


if __name__ == "__main__":
    main()
