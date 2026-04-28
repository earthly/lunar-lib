#!/bin/bash
# cronos-runner-check.sh — agent-after-file-edit validation.
#
# Fires when a `.github/workflows/*.yml` file is edited. If the file's
# repo lives in a cronos org (e.g. `pantalasa-cronos/<repo>`), the
# workflow MUST have at least one job with `runs-on: cronos` (or a
# matrix list that includes `cronos`). Otherwise the lunar agent never
# sees the CI runs and any CI-hook collectors registered for the repo
# silently never fire — which has bitten ENG-543: a worker shipped a
# scala-service repo with no workflow at all and then invented a
# "per-component cycle hasn't reached the repo yet" excuse rather than
# pushing a triggering CI workflow.
#
# Args:
#   $1 — absolute path to the edited workflow file
#
# Exit:
#   0 = pass (not a cronos-org repo, OR has cronos runner)
#   1 = fail (cronos-org repo with no cronos runner — message surfaces)

set -u

FILE_PATH="${1:-}"
[ -z "$FILE_PATH" ] && exit 0
[ -f "$FILE_PATH" ] || exit 0

# Determine the org by asking git from the file's directory. If the file
# isn't inside a git working tree (e.g. someone editing a workflow
# template inside lunar-lib itself), skip — we have no way to know what
# repo it'll end up in.
FILE_DIR=$(dirname "$FILE_PATH")
REMOTE_URL=$(git -C "$FILE_DIR" config --get remote.origin.url 2>/dev/null)
[ -z "$REMOTE_URL" ] && exit 0

# Match cronos orgs from common URL shapes:
#   git@github.com:pantalasa-cronos/scala-service.git
#   https://github.com/pantalasa-cronos/scala-service
# The org segment is everything between the host separator and the next
# `/`. We treat any org name containing `cronos` (case-insensitive) as a
# cronos-runner-requiring org.
ORG=$(echo "$REMOTE_URL" | sed -E 's|^.*[/:]([^/]+)/[^/]+(\.git)?/?$|\1|')
echo "$ORG" | grep -qiE 'cronos' || exit 0

# At this point we know the workflow is destined for a cronos-org repo.
# Require at least one `runs-on:` whose value includes `cronos`.
# Matches:
#   runs-on: cronos
#   runs-on: [cronos, self-hosted]
#   runs-on: ${{ matrix.runner }}   ← skipped (we can't statically resolve)
if grep -qE '^\s*runs-on:.*\$\{\{' "$FILE_PATH"; then
  # At least one runs-on uses an expression — assume the author knows
  # what they're doing and don't second-guess. Better than false
  # positives on legitimate matrix builds.
  exit 0
fi

if grep -qE '^\s*runs-on:.*\bcronos\b' "$FILE_PATH"; then
  exit 0
fi

cat >&2 <<EOF
Workflow $FILE_PATH lives in cronos org "$ORG" but no job uses
\`runs-on: cronos\`. The lunar agent only traces CI commands on the
cronos self-hosted runner — without it, every CI-hook collector
registered for this component will silently never fire, and the
component will look "stuck" in the hub even though the repo is
registered correctly.

Fix: set \`runs-on: cronos\` on the job(s) that should be traced
(typically all of them in a cronos-org repo).
EOF
exit 1
