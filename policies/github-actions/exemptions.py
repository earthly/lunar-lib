"""Shared parsing and matching for the `exempt_jobs` policy input.

An exemption records an accepted risk against one workflow job. It never turns a
finding into a pass: the check still reports every finding that is not exempted,
and resolves to `skip` — naming each job and its reason — only when every finding
it made was exempted.
"""

import os


class ExemptionConfigError(ValueError):
    """A malformed `exempt_jobs` value.

    Raised rather than skipped so a typo can never read as "exempt everything".
    """


class Exemption:
    """One `<workflow-file>:<job-id> = <reason>` entry."""

    def __init__(self, workflow, job, reason):
        self.workflow = workflow
        self.job = job
        self.reason = reason

    @property
    def target(self):
        return f"{self.workflow}:{self.job}"

    def __str__(self):
        return f"{self.target} — {self.reason}"

    def matches(self, wf_file, job_name):
        if job_name != self.job:
            return False
        return self.matches_workflow(wf_file)

    def matches_workflow(self, wf_file):
        # The collector emits the path it found (`.github/workflows/ci.yml`);
        # accept the bare filename too, since that is how people name workflows.
        return self.workflow in (wf_file, os.path.basename(wf_file))


def parse_exempt_jobs(raw):
    """Parse the `exempt_jobs` input — one `<workflow-file>:<job-id> = <reason>`
    per line, `#` comments and blank lines ignored.

    Raises ExemptionConfigError on anything else.
    """
    exemptions = []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        target, sep, reason = line.partition("=")
        if not sep:
            raise ExemptionConfigError(
                f"exempt_jobs line {lineno}: expected "
                f"'<workflow-file>:<job-id> = <reason>', got {line!r}"
            )

        reason = reason.strip()
        if not reason:
            raise ExemptionConfigError(
                f"exempt_jobs line {lineno}: a reason is required — an "
                f"exemption records why the risk was accepted"
            )

        # rpartition: workflow paths carry no colon, job ids cannot.
        workflow, sep, job = target.strip().rpartition(":")
        if not sep or not workflow or not job:
            raise ExemptionConfigError(
                f"exempt_jobs line {lineno}: expected "
                f"'<workflow-file>:<job-id>' before '=', got {target.strip()!r}"
            )

        exemptions.append(Exemption(workflow, job, reason))

    return exemptions


def find_exemption(exemptions, wf_file, job_name):
    for e in exemptions:
        if e.matches(wf_file, job_name):
            return e
    return None


def stale_exemptions(exemptions, workflows):
    """Entries naming a workflow this component has, but a job it does not define.

    An entry whose workflow file is absent from the component is left alone: one
    policy entry is normally shared by every component in its scope, so "not my
    workflow" is the common case rather than a misconfiguration.
    """
    stale = []
    for e in exemptions:
        seen_workflow = False
        for wf in workflows:
            if not isinstance(wf, dict):
                continue
            if not e.matches_workflow(wf.get("file", "")):
                continue
            seen_workflow = True
            jobs = wf.get("jobs", {})
            if isinstance(jobs, dict) and e.job in jobs:
                break
        else:
            if seen_workflow:
                stale.append(e)
    return stale


def format_exemptions(exemptions, limit=5):
    """Render exemptions for a check message, one line each.

    Deduplicated by target: a job with two offending checkout steps matches the
    same entry twice, and naming it twice would read as two exemptions.
    """
    unique = []
    seen = set()
    for e in exemptions:
        if e.target in seen:
            continue
        seen.add(e.target)
        unique.append(e)

    shown = "; ".join(str(e) for e in unique[:limit])
    if len(unique) > limit:
        shown += f" (and {len(unique) - limit} more)"
    return shown
