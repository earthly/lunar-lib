"""Shared parsing and matching for the `exempt_jobs` policy input.

An exemption records that a job's finding has been reviewed and accepted. It
never turns a finding into a pass: the check still reports every finding that is
not exempt, and resolves to `skip` — naming each exempted job — only when every
finding it made was exempted.
"""

import os


class ExemptionConfigError(ValueError):
    """A malformed `exempt_jobs` value.

    Raised rather than skipped so a typo can never read as "exempt everything".
    """


class Exemption:
    """One `<workflow-file>:<job-id>` entry."""

    def __init__(self, workflow, job):
        self.workflow = workflow
        self.job = job

    @property
    def target(self):
        return f"{self.workflow}:{self.job}"

    def __str__(self):
        return self.target

    def matches(self, wf_file, job_name):
        return job_name == self.job and self.matches_workflow(wf_file)

    def matches_workflow(self, wf_file):
        # The collector emits the path it found (`.github/workflows/ci.yml`);
        # accept the bare filename too, since that is how people name workflows.
        return self.workflow in (wf_file, os.path.basename(wf_file))


def parse_exempt_jobs(raw):
    """Parse the `exempt_jobs` input — `<workflow-file>:<job-id>` entries
    separated by newlines or commas. Blank entries are ignored, and a `#`
    comments out the rest of its line, so the rationale can sit next to the
    entry it explains — including a rationale containing a comma, which is why
    comments are stripped per line and only then split on commas.

    Raises ExemptionConfigError on anything else.
    """
    entries = []
    for line in raw.splitlines():
        entries.extend(line.split("#", 1)[0].split(","))

    exemptions = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # rpartition: workflow paths carry no colon, job ids cannot.
        workflow, sep, job = entry.rpartition(":")
        if not sep or not workflow or not job:
            raise ExemptionConfigError(
                f"exempt_jobs: expected '<workflow-file>:<job-id>', got {entry!r}"
            )

        exemptions.append(Exemption(workflow, job))

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
    """Render exemptions for a check message.

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
