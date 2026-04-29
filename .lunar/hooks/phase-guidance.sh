#!/bin/bash
# phase-guidance.sh — agent-session-start hook.
# Stdin: SessionStart JSON ({ source, cwd }). Ignored — content is static.
# Stdout: markdown additionalContext routing the agent to the right
# phase doc for whatever phase their current PR / ticket sits in.
#
# The playbook lives in .ai-implementation/, split across one overview
# (LUNAR-PLUGIN-PLAYBOOK-AI.md) and four phase-specific docs under
# phases/. Each phase doc is self-contained for that phase. This hook
# tells the agent how to figure out the phase and which phase doc to
# read first — keeping their context fresh and focused on the work
# actually in front of them.

cat <<'EOF'
## Where are you in the PR lifecycle?

Before doing any substantive work on a PR-related session, identify
which phase the work is in and read the matching phase doc. Each phase
has its own checklist and its own definition of "done" — finishing one
phase is usually NOT the same as finishing the work.

| Signal | Phase | Read |
|---|---|---|
| PR title contains `[Spec Only]` / `[Spec]`; no scripts (`*.sh`) in `collectors/<name>/`, no `*.py` in `policies/<name>/` | **Spec** | `.ai-implementation/phases/spec.md` |
| Spec approved by the secondary reviewer (e.g. Vlad); implementation not yet written, or just being written; cronos test evidence not yet posted on the PR | **Implementation & testing** | `.ai-implementation/phases/implementation.md` (read NOW — implementation and testing are one unbroken unit) |
| Implementation present; cronos test evidence posted on the PR; awaiting both approvals | **Implementation review** | `.ai-implementation/phases/impl-review.md` |
| Both required reviewers approved; CI green | **Merge** | `.ai-implementation/phases/merge.md` |

For lifecycle context, conventions, and cross-cutting common mistakes
that apply to every phase, see
`.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md`. You don't have to
read it cover-to-cover up front, but you should at least skim it and
read the matching phase doc above before starting work on that phase.

**Critical**: "CI green" is not the finish line for implementation PRs.
`phases/implementation.md` requires a full cronos round-trip (deploy
branch ref to cronos, trigger collection, gather JSON evidence, post
screenshots) before the PR is ready for final review. Running
`lunar collector dev` locally is not sufficient for CI-hook collectors
— those only fire during actual CI on cronos.

**How to check your phase right now:**
1. `gh pr view <PR> --json title,reviews,mergeable` to see PR title, approvals, CI status.
2. `ls collectors/<name>/ policies/<name>/` on the branch to see what's implemented.
3. Look at the PR comments — has cronos test evidence been posted? That's the implementation → impl-review transition signal.
4. If the PR transitioned (title changed, new approval came in, evidence posted), the previous phase's checklist no longer applies — re-check the table and switch phase docs.
EOF
