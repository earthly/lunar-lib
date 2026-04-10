from lunar_policy import Check

# Expressions that reference PR head code
PR_HEAD_PATTERNS = [
    "github.event.pull_request.head.sha",
    "github.event.pull_request.head.ref",
    "github.head_ref",
]


def main(node=None):
    c = Check(
        "no-dangerous-trigger-checkout",
        "No pull_request_target workflows checking out PR head code",
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
            triggers = wf.get("triggers", [])
            if not isinstance(triggers, list):
                continue
            if "pull_request_target" not in triggers:
                continue

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

                    with_params = step.get("with", {})
                    if not isinstance(with_params, dict):
                        continue
                    ref = with_params.get("ref", "")
                    if not isinstance(ref, str):
                        continue

                    for pattern in PR_HEAD_PATTERNS:
                        if pattern in ref:
                            findings.append(
                                f"{wf_file}: pull_request_target workflow "
                                f"checks out PR head ref in job '{job_name}'"
                            )
                            break

        if findings:
            details = "; ".join(findings[:5])
            suffix = (
                f" (and {len(findings) - 5} more)" if len(findings) > 5 else ""
            )
            c.fail(
                f"{len(findings)} dangerous checkout(s) found — "
                f"{details}{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
