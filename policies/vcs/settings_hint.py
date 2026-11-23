"""The rerun hint for a vcs check that fails on a repository setting. A
repository admin can change the setting without a commit, and a `/lunar rerun`
comment on the pull request then re-collects it."""

from rerun_hint import hint, in_pull_request

BRANCH_PROTECTION = "branch-protection"
REPOSITORY = "repository"

# Matches the manifest default, which `lunar policy dev` doesn't apply.
DEFAULT_RERUN_COLLECTORS = "auto"
SENTENCE = ("Once a repository admin changes it, comment {command} to re-check "
            "without a new commit.")


def with_hint(c, message, sub_collector):
    """`message`, ending with the rerun hint on a pull request. `auto` reruns the
    provider collector's sub-collector that records the setting, under the
    provider's own name (github.branch-protection, gitlab.repository)."""
    if not in_pull_request():
        return message
    provider = str(c.get_value_or_default(".vcs.provider", "") or "")
    text = hint(SENTENCE, DEFAULT_RERUN_COLLECTORS,
                f"{provider}.{sub_collector}" if provider else None)
    if not text:
        return message
    return message + ("" if message.endswith(".") else ".") + text
