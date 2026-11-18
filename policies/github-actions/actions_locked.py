"""Check that third-party actions can't be moved to different code.

A tag or branch can be repointed by whoever controls the action's repository.
A reference is fixed when it pins a full-length commit SHA, or when the
workflow's entry in .github/workflows/actions.lock (written by
`gh actions-lock`, enforced by the runner) lists it.
"""

import re

from lunar_policy import Check

FULL_SHA = re.compile(r"[0-9a-fA-F]{40}")


def is_reusable_workflow(name):
    return "/.github/workflows/" in name


def lock_key(uses):
    """How gh actions-lock keys a reference: owner/repo lowercased, any sub-path
    dropped (it locks the repository), and the ref as written unless it's a
    full SHA. Tags and branches are case-sensitive, like git."""
    target, _, ref = uses.partition("@")
    nwo = "/".join(target.split("/")[:2]).lower()
    if FULL_SHA.fullmatch(ref):
        ref = ref.lower()
    return f"{nwo}@{ref}"


def main(node=None):
    c = Check(
        "actions-locked",
        "All third-party actions are pinned to a commit SHA or locked in actions.lock",
        node=node,
    )
    with c:
        gha_node = c.get_node(".ci.native.github_actions")
        if not gha_node.exists():
            c.skip("No GitHub Actions data available")

        gha = gha_node.get_value()
        workflows = gha.get("workflows") if isinstance(gha, dict) else None
        if not isinstance(workflows, list):
            c.skip("No workflow data available")

        # Written in the same collect call as the workflows, so its absence is
        # final; reading it as a sub-node would pend until collection finishes.
        lockfile = gha.get("lockfile")
        locked_by_file = {}
        if isinstance(lockfile, dict) and isinstance(lockfile.get("workflows"), dict):
            locked_by_file = lockfile["workflows"]

        seen = set()
        for wf in workflows:
            if not isinstance(wf, dict):
                continue
            wf_file = wf.get("file", "<unknown>")
            locked = locked_by_file.get(wf_file)
            locked = {lock_key(u) for u in locked if isinstance(u, str)} if isinstance(locked, list) else set()

            for action in wf.get("actions") or []:
                if not isinstance(action, dict):
                    continue
                if action.get("party") == "1st" or action.get("pinning") == "sha":
                    continue
                name = action.get("name", "")
                uses = action.get("uses") or f"{name}@{action.get('ref', '')}"
                if (wf_file, uses) in seen:
                    continue
                seen.add((wf_file, uses))

                # The lockfile doesn't cover reusable workflows, so only a SHA fixes one.
                if is_reusable_workflow(name):
                    c.fail(
                        f"'{wf_file}' calls '{uses}', which isn't pinned to a commit. "
                        f"Pin it to a full-length commit SHA; actions.lock doesn't cover "
                        f"reusable workflows."
                    )
                elif lock_key(uses) not in locked:
                    c.fail(
                        f"'{wf_file}' uses '{uses}', which isn't pinned to a commit. "
                        f"Pin it to a full-length commit SHA, or lock it with gh actions-lock."
                    )

    return c


if __name__ == "__main__":
    main()
