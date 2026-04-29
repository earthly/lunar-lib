# Phase: Merge

You are in the **merge** phase of a lunar-lib plugin PR. Both reviewers
approved. CI is green. Test evidence is posted. Time to ship.

```text
Spec → ... → Implement & test → Evidence posted → Impl review → Approval → [Merge]
                                                                              ▲ you are here
```

For lifecycle context, conventions, and cross-cutting common mistakes,
see [`LUNAR-PLUGIN-PLAYBOOK-AI.md`](../LUNAR-PLUGIN-PLAYBOOK-AI.md).

---

## Pre-merge checklist

- [ ] CI is green
- [ ] Claude review comments addressed
- [ ] **Both reviewers approved** the implementation
- [ ] Test results with JSON output + screenshots posted on PR
- [ ] No unresolved review threads
- [ ] Cronos config cleaned up (no branch refs remaining)
- [ ] `default_image` reverted to `-main` tag (if custom Earthfile)

The last two items overlap with the tail of the testing checklist in
[`phases/implementation.md`](implementation.md) (steps 12–14). If you
haven't already cleaned up the cronos branch ref and reverted
`default_image`, do that now — branch references in the cronos config
will break manifest syncs once the branch is deleted on merge.

---

## Squash-merge

Squash-merge the PR and delete the branch.

---

## Post-merge: contribute back to cronos

**For NEW plugins:** re-add the collector/policy to `pantalasa-cronos/lunar/lunar-config.yml`, now referencing `@main`:

```yaml
- uses: github://earthly/lunar-lib/collectors/<name>@main
```

Commit, push, and **verify the sync-manifest CI build passes**.

**For EXISTING plugins:** the config already points to `@main`, so nothing to do.

---

## Clean up

1. Delete the worktree/branch locally.
2. Write down what you learned — append to your learning journal.
3. Close the Linear ticket if still open.

---

## What's next

The PR lifecycle is complete. If reviewers asked for follow-ups in
separate tickets/PRs, pick those up next. Otherwise, return to the
[growth roadmap](../growth-roadmap.md) for the next prioritized plugin.
