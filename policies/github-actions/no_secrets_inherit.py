from lunar_policy import Check


def main(node=None):
    c = Check(
        "no-secrets-inherit",
        "No reusable workflow calls use secrets: inherit",
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
                # Reusable workflow calls have uses: at job level
                if not job.get("uses"):
                    continue
                if job.get("secrets") == "inherit":
                    findings.append(
                        f"{wf_file}: job '{job_name}' uses secrets: inherit"
                    )

        if findings:
            details = "; ".join(findings[:5])
            suffix = (
                f" (and {len(findings) - 5} more)" if len(findings) > 5 else ""
            )
            c.fail(
                f"{len(findings)} secrets: inherit usage(s) found — "
                f"{details}{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
