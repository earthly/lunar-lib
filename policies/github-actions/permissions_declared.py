from lunar_policy import Check


def main(node=None):
    c = Check(
        "permissions-declared",
        "All workflows declare explicit permissions",
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

        missing = []
        for wf in workflows:
            wf_file = wf.get("file", "<unknown>")

            # Workflow-level permissions present — OK
            if wf.get("permissions") is not None:
                continue

            # No workflow-level permissions — check if ALL jobs declare them
            jobs = wf.get("jobs", {})
            if not isinstance(jobs, dict):
                missing.append(wf_file)
                continue

            jobs_without = [
                name
                for name, job in jobs.items()
                if isinstance(job, dict) and job.get("permissions") is None
            ]
            if jobs_without:
                missing.append(wf_file)

        if missing:
            files = ", ".join(missing[:5])
            suffix = (
                f" (and {len(missing) - 5} more)" if len(missing) > 5 else ""
            )
            c.fail(
                f"{len(missing)} workflow(s) missing permissions declaration — "
                f"{files}{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
