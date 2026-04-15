import re

from lunar_policy import Check

# GitHub Actions contexts that can be controlled by external actors.
# See: https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#understanding-the-risk-of-script-injections
DANGEROUS_PREFIXES = [
    "github.event.issue.title",
    "github.event.issue.body",
    "github.event.pull_request.title",
    "github.event.pull_request.body",
    "github.event.pull_request.head.ref",
    "github.event.pull_request.head.label",
    "github.event.comment.body",
    "github.event.review.body",
    "github.event.review_comment.body",
    "github.event.discussion.title",
    "github.event.discussion.body",
    "github.event.head_commit.message",
    "github.event.head_commit.author.email",
    "github.event.head_commit.author.name",
    "github.head_ref",
    # Array-indexed fields (match prefix before the index)
    "github.event.commits[",
    "github.event.pages[",
]

EXPR_PATTERN = re.compile(r"\$\{\{\s*(.+?)\s*\}\}")


def _is_dangerous(expr):
    expr = expr.strip()
    for prefix in DANGEROUS_PREFIXES:
        if expr.startswith(prefix):
            return True
    return False


def main(node=None):
    c = Check(
        "no-script-injection",
        "No attacker-controlled expressions in run blocks or scripts",
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
                    step_name = step.get("name", "<unnamed>")

                    # Check run: blocks
                    run_block = step.get("run")
                    if isinstance(run_block, str):
                        for m in EXPR_PATTERN.finditer(run_block):
                            if _is_dangerous(m.group(1)):
                                findings.append(
                                    f"{wf_file}: job '{job_name}', step "
                                    f"'{step_name}' uses "
                                    f"{m.group(1).strip()} in run block"
                                )

                    # Check actions/github-script script: field
                    uses = step.get("uses", "")
                    if isinstance(uses, str) and "actions/github-script" in uses:
                        with_params = step.get("with", {})
                        if isinstance(with_params, dict):
                            script = with_params.get("script", "")
                            if isinstance(script, str):
                                for m in EXPR_PATTERN.finditer(script):
                                    if _is_dangerous(m.group(1)):
                                        findings.append(
                                            f"{wf_file}: job '{job_name}', "
                                            f"step '{step_name}' uses "
                                            f"{m.group(1).strip()} in "
                                            f"github-script"
                                        )

        if findings:
            details = "; ".join(findings[:5])
            suffix = (
                f" (and {len(findings) - 5} more)" if len(findings) > 5 else ""
            )
            c.fail(
                f"{len(findings)} injectable expression(s) found — "
                f"{details}{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
