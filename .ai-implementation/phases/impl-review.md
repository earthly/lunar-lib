# Phase: Implementation Review

You are in the **implementation review** phase of a lunar-lib plugin PR.
Test evidence is posted on the PR. You're now waiting for **both
reviewers** to approve via GitHub review.

```text
Spec → ... → Implement & test → Evidence posted → [Impl review] → Approval → Merge
                                                       ▲ you are here
```

When **both** reviewers approve, switch to
[`phases/merge.md`](merge.md). Until then, you stay here addressing
review feedback.

For lifecycle context, conventions, and cross-cutting common mistakes,
see [`LUNAR-PLUGIN-PLAYBOOK-AI.md`](../LUNAR-PLUGIN-PLAYBOOK-AI.md).

---

> **Precondition: you have posted test evidence on the PR (Step 8 of
> [`phases/implementation.md`](implementation.md)).** If you haven't —
> if you're here because you pushed implementation code and CI went
> green — you are not ready for this phase. Go back to the
> implementation phase and finish the testing checklist. Implementation
> review does not start until evidence is posted.

---

## What to do here

CodeRabbit reviews the PR once the Bender server posts `@coderabbitai review` on your behalf — that's triggered automatically when a human flips the PR out of draft (see [`phases/implementation.md`](implementation.md) Step 0). If CodeRabbit hasn't reviewed by the time you're seeing this phase, it most likely means the PR is still in draft or the ready-for-review event came from a bot rather than a human; ask the requester to retoggle ready or check the server logs for `[coderabbit-summon]`. Once summoned, CodeRabbit re-reviews on subsequent pushes automatically.

Address its feedback, but **use judgment** — CodeRabbit sometimes flags things that aren't real issues. If a comment is wrong or irrelevant, reply explaining why and resolve the thread. When you've addressed a valid comment (pushed a fix), resolve that thread too. Don't leave conversations hanging.

**Implementation review may trigger spec changes.** Reviewers may ask you to adjust the YAML manifest, README, or Component JSON paths even after implementation is added. This is normal — make the changes. **Re-test after significant changes** (logic changes, new assertions, changed Component JSON paths). A quick `lunar collector dev` or `lunar policy dev` run is enough — post updated results on the PR if the previous results are now stale. See the testing steps in [`phases/implementation.md`](implementation.md) if you need a refresher.

Wait for **both reviewers** to approve the PR via GitHub review.

**While waiting:**
- Fix CI failures automatically.
- Address review comments. Push fixes. Reply to reviewers on the PR.
- If reviewers are discussing with each other, wait for them to reach a conclusion before acting.
- **Do not merge** until you have both approvals.

---

## What's next

| Trigger | Read next |
|---|---|
| Both reviewers approved + CI green | [`phases/merge.md`](merge.md) — pre-merge checklist, squash-merge, post-merge contribute back to cronos |
| Reviewer asked for code changes that affect the JSON your collector writes | Re-test on cronos before re-requesting review (see Step 5 in [`phases/implementation.md`](implementation.md)) |
| Reviewer asked for spec changes | Skim [`phases/spec.md`](spec.md) for the rules you need to revisit, make the changes, re-test, repost evidence |
