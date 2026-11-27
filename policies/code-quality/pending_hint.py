"""The rerun hint for a code-quality check that fails because the scanner hadn't
reported on the commit yet. Once it has, a `/lunar rerun` comment on the pull
request re-collects its results."""

from rerun_hint import hint, in_pull_request

# Matches the manifest default, which `lunar policy dev` doesn't apply.
DEFAULT_RERUN_COLLECTORS = "auto"
SENTENCE = ("The scanner hadn't reported on this commit when Lunar checked. "
            "Once it has, comment {command}.")


def with_pending_hint(c, message):
    """`message`, ending with the rerun hint on a pull request whose scanner
    recorded its analysis as pending (.code_quality.source.analysis_status).
    `auto` reruns that scanner's collector under its own name
    (.code_quality.source.tool, e.g. sonarqube)."""
    if not in_pull_request():
        return message
    if c.get_value_or_default(".code_quality.source.analysis_status", None) != "pending":
        return message
    tool = str(c.get_value_or_default(".code_quality.source.tool", "") or "")
    return message + hint(SENTENCE, DEFAULT_RERUN_COLLECTORS, tool or None)
