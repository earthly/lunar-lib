#!/bin/bash
# phase-guidance.sh — agent-session-start hook.
# Stdin: SessionStart JSON ({ source, cwd }). Ignored — content is static.
# Stdout: markdown additionalContext routing the agent to the right
# playbook section for whatever phase their current PR / ticket sits in.
#
# Keeps the playbook as single source of truth (deep content lives in
# .ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md); this script just tells
# the agent how to figure out the phase and which section to read.

cat <<'EOF'
## Where are you in the PR lifecycle?

Before doing any substantive work on a PR-related session, identify which
phase the work is in and read the matching playbook section. Each phase
has a different checklist, and finishing one phase is usually NOT the
same as finishing the work.

| Signal | Phase | Read in `.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md` |
|---|---|---|
| PR title contains `[Spec Only]` / `[Spec]`; no scripts (`*.sh`) in `collectors/<name>/`, no `*.py` in `policies/<name>/` | **Spec review** | `## Spec PR` + `### Then wait for go-ahead` |
| Spec approved by secondary reviewer (e.g. Vlad); implementation not yet written | **Transitioning to implementation** | `## Implementation (same PR)` + entirety of `## Testing` |
| PR title no longer has `[Spec Only]`; implementation scripts/policies present; CI running or green | **Implementation review** | `## Testing` (14 steps) + `## Integration Test Evidence` |
| All required reviewers approved; CI green | **Ready to merge** | `### Merge` (end of playbook) |

**Critical**: "CI green" is not the finish line for implementation PRs.
The playbook's `## Testing` section requires a full cronos round-trip
(deploy branch ref to cronos, trigger collection, gather JSON evidence,
post screenshots) before the PR is ready for final review. Running
`lunar collector dev` locally is not sufficient for CI-hook collectors
— those only fire during actual CI on cronos.

**How to check your phase right now:**
1. `gh pr view <PR> --json title,reviews,mergeable` to see PR title, approvals, CI status.
2. `ls collectors/<name>/ policies/<name>/` on the branch to see what's implemented.
3. If the PR transitioned (title changed, new approval came in), the
   previous phase's checklist no longer applies.
EOF
