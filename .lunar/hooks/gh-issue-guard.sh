#!/bin/bash
# gh-issue-guard.sh — agent-before-command hook for the `gh` CLI.
#
# Blocks `gh issue create|edit|delete|transfer|develop|lock|unlock` and
# `gh label create|edit|delete|clone` and the raw-API equivalents.
# Issue tracking for earthly projects lives in Linear, not GitHub; any
# ticket-like thing the agent wants to create must go through
# `bender-linear-create-issue` instead.
#
# Read-only gh operations and everything under `gh pr`, `gh repo`, `gh
# run`, `gh workflow`, etc. remain unrestricted.
#
# Exit 0 = allow, Exit 2 = block (stderr rendered to the agent).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r ".tool_input.command // empty")

# Scope to real `gh` invocations, same technique as lunar-cli-guard.sh:
# match `gh` at a command-word boundary (line start or after `&`/`|`/`;`),
# NOT after plain whitespace (which would match `gh` inside quoted
# strings in echo/printf/--body arguments).
#
# Before matching, strip leading `FOO=bar ` env assignments so an LLM
# can't bypass the block with `FOO=1 gh issue create ...`. Those
# assignments only affect the child process's env, not the hook's
# authority over whether the binary runs.
NORMALIZED=$(echo "$COMMAND" | sed -E 's/(^|[\&\|\;])[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)+/\1/g')
GH_INVOCATIONS=$(echo "$NORMALIZED" | grep -oE '(^|[\&\|\;])[[:space:]]*gh([[:space:]][^|&;]*)?' | sed -E 's/^[[:space:]&|;]*//')
[ -z "$GH_INVOCATIONS" ] && exit 0

# For each gh invocation, decide: allow or block?
while IFS= read -r INVOCATION; do
  [ -z "$INVOCATION" ] && continue

  # Trim and split into first two argv tokens (the subcommand + verb).
  # `gh issue create ...` → SUB="issue", VERB="create"
  # `gh api ...`          → SUB="api",   VERB=<first non-flag arg>
  read -r GH_BIN SUB VERB REST <<< "$INVOCATION"

  # `gh --help` / `gh --version` / bare `gh` → allow.
  if [ -z "$SUB" ] || [[ "$SUB" == --* ]] || [[ "$SUB" == -* ]]; then
    continue
  fi

  case "$SUB" in
    issue)
      case "$VERB" in
        create|edit|delete|transfer|develop|lock|unlock)
          echo "Blocked: \`gh issue $VERB\` creates or mutates a GitHub issue." >&2
          echo "" >&2
          echo "Issue tracking for earthly projects lives in Linear, not GitHub." >&2
          echo "To create a ticket, use \`bender-linear-create-issue\` instead:" >&2
          echo "" >&2
          echo "  bender-linear-create-issue \\" >&2
          echo "    --project c4a71ff10119 \\    # lunar-lib slug; adjust per project" >&2
          echo "    --title \"...\" \\" >&2
          echo "    --description-file /tmp/desc.md \\" >&2
          echo "    [--labels chore,feature] [--priority 3]" >&2
          echo "" >&2
          echo "If you genuinely need to interact with an EXISTING GitHub issue" >&2
          echo "(view, comment, close, reopen), that's allowed — those subcommands" >&2
          echo "aren't blocked. This hook only blocks creating / editing tickets" >&2
          echo "that should be Linear-resident." >&2
          exit 2
          ;;
      esac
      ;;
    label)
      case "$VERB" in
        create|edit|delete|clone)
          echo "Blocked: \`gh label $VERB\` mutates the GitHub repo's label set." >&2
          echo "" >&2
          echo "Labels for ticket/priority tracking belong on the Linear side." >&2
          echo "If you need a Linear label, create it in the Linear UI or via the" >&2
          echo "Linear API — don't mirror labels into GitHub repos; they diverge." >&2
          echo "" >&2
          echo "Read-only \`gh label list\` remains allowed." >&2
          exit 2
          ;;
      esac
      ;;
    api)
      # Block raw-API shortcuts that do the same thing, e.g.:
      #   gh api repos/earthly/lunar-lib/issues -X POST -f title=...
      #   gh api -X POST /repos/earthly/lunar-lib/labels -f name=chore
      #   gh api graphql -f query='mutation { issueCreate(...) { ... } }'
      #
      # Two fire-together checks:
      #   (a) REST: explicit -X POST/PATCH/PUT/DELETE on a /issues or
      #       /labels path.
      #   (b) GraphQL: `gh api graphql` plus a known mutation name in
      #       the surrounding command text. gh api's graphql subcommand
      #       uses POST implicitly, so a blanket -X check would miss it.
      # We check (b) against the FULL $COMMAND (not just $INVOCATION)
      # because the mutation string is often on a continuation line.

      # (a) REST mutations.
      if echo "$INVOCATION" | grep -qE '(^|[[:space:]])-X[[:space:]]+(POST|PATCH|PUT|DELETE)([[:space:]]|$)'; then
        if echo "$INVOCATION" | grep -qE '/(issues|labels)(\?|[[:space:]]|$|/)'; then
          METHOD=$(echo "$INVOCATION" | grep -oE '\-X[[:space:]]+(POST|PATCH|PUT|DELETE)' | head -1 | awk '{print $2}')
          echo "Blocked: \`gh api -X $METHOD\` on a /issues or /labels endpoint." >&2
          echo "" >&2
          echo "This is the raw-API equivalent of \`gh issue create\` / \`gh label create\`," >&2
          echo "which also lives in Linear for earthly projects. Use" >&2
          echo "\`bender-linear-create-issue\` for tickets; leave GitHub labels alone." >&2
          exit 2
        fi
      fi

      # (b) GraphQL mutations. `gh api graphql` always posts; the mutation
      # we care about is identified by an issueCreate / createLabel /
      # addLabelsToLabelable style verb in the surrounding command. We
      # match against $COMMAND so multi-line heredocs or `-f query=...`
      # on a continuation still get caught.
      if echo "$INVOCATION" | grep -qE '(^|[[:space:]])graphql([[:space:]]|$)'; then
        if echo "$COMMAND" | grep -qE '(mutation[[:space:]]*\{|"?query"?[[:space:]]*:[[:space:]]*"mutation)' && \
           echo "$COMMAND" | grep -qiE '(issueCreate|issueUpdate|issueDelete|createIssue|updateIssue|deleteIssue|createLabel|updateLabel|deleteLabel|addLabelsToLabelable|removeLabelsFromLabelable)'; then
          echo "Blocked: \`gh api graphql\` with an issue/label mutation." >&2
          echo "" >&2
          echo "Use \`bender-linear-create-issue\` for tickets. GitHub labels/issues" >&2
          echo "for earthly projects are not the source of truth." >&2
          exit 2
        fi
      fi
      ;;
  esac
done <<< "$GH_INVOCATIONS"

exit 0
