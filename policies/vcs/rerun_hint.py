"""The `/lunar rerun` hint a policy appends to a failure the PR author can fix
without a new commit. The Hub packages one plugin directory, so each policy
that uses it keeps an identical copy (scripts/validate_shared_modules.py).

`rerun_collectors` names the collectors to rerun, as the configuration imports
them. "" leaves the hint out, for a Hub that doesn't accept the comment, and
`auto` stands for the collector the caller says recorded the data.
"""

import os
import re
import sys

from lunar_policy import variable_or_default

# A name `/lunar rerun` accepts: a collector import's name, alone or with a
# sub-collector ("jira", "jira.ticket"). The character set also keeps a name
# inside the code span the hint renders it in.
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def hint(sentence, default, auto=None):
    """`sentence` with {command} filled in by the `/lunar rerun` comment, led by
    a space so it can follow a failure message, or "" for no hint. `auto` in
    the input becomes `auto` here, and drops out when that's None.

    The hint never changes a verdict: a malformed name leaves it out, with the
    reason in the run log, rather than turning a failure into an error."""
    raw = variable_or_default("rerun_collectors", default)
    names = []
    for name in re.split(r"[\s,]+", raw):
        if name == "auto":
            name = auto or ""
        if name and name not in names:
            names.append(name)
    bad = [n for n in names if not NAME.fullmatch(n)]
    if bad:
        print(f"rerun_collectors: no rerun hint, not a collector name: {', '.join(bad)}",
              file=sys.stderr)
        return ""
    if not names:
        return ""
    return " " + sentence.format(command=f"`/lunar rerun {','.join(names)}`")


def in_pull_request():
    """Whether this evaluation is for a pull request, the only place the comment
    can go. A check that also runs on the default branch hints only here."""
    return os.environ.get("LUNAR_COMPONENT_PR", "") not in ("", "0")
