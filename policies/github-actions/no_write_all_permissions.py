from lunar_policy import Check


def _is_write_all(perms):
    """Check if permissions value represents write-all."""
    return isinstance(perms, str) and perms.strip().lower() == "write-all"


def main(node=None):
    c = Check(
        "no-write-all-permissions",
        "No workflows or jobs use permissions: write-all",
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

            # Check workflow-level permissions
            if _is_write_all(wf.get("permissions")):
                findings.append(
                    f"{wf_file}: workflow-level permissions: write-all"
                )

            # Check job-level permissions
            jobs = wf.get("jobs", {})
            if not isinstance(jobs, dict):
                continue
            for job_name, job in jobs.items():
                if isinstance(job, dict) and _is_write_all(job.get("permissions")):
                    findings.append(
                        f"{wf_file}: job '{job_name}' has "
                        f"permissions: write-all"
                    )

        if findings:
            details = "; ".join(findings[:5])
            suffix = (
                f" (and {len(findings) - 5} more)" if len(findings) > 5 else ""
            )
            c.fail(
                f"{len(findings)} write-all permission(s) found — "
                f"{details}{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
