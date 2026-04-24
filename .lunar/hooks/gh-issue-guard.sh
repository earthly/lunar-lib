#!/bin/bash
# gh-issue-guard.sh — agent-before-command hook for the `gh` CLI.
#
# Blocks `gh issue create|edit|delete|transfer|develop|lock|unlock` and
# `gh label create|edit|delete|clone` and the raw-API equivalents.
# Issue tracking for earthly projects lives in Linear, not GitHub; any
# ticket-like thing the agent wants to create must go through
# `bender-linear-create-issue` instead.
#
# Read-only gh operations, comment/close/reopen on EXISTING issues, and
# everything under `gh pr`, `gh repo`, `gh run`, `gh workflow`, etc.
# remain unrestricted.
#
# Exit 0 = allow, Exit 2 = block (stderr rendered to the agent).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r ".tool_input.command // empty")

# ---------- Scope to real `gh` invocations ----------
#
# Match `gh` at a command-word boundary — same technique as
# lunar-cli-guard.sh. Command-word boundaries include:
#   - line start
#   - after `&`, `|`, `;`         (command chaining / backgrounding)
#   - after `(` or backtick       (command substitution: `$(gh ...)`, backtick-gh-backtick)
# We deliberately DO NOT match after plain whitespace, which would
# flag `gh` inside quoted strings (echo/printf/--body arguments,
# commit messages, etc.).
#
# Before matching, strip leading `FOO=bar ` env assignments so an LLM
# can't bypass the block with `FOO=1 gh issue create ...`. Those
# assignments only affect the child process's env, not the hook's
# authority over whether the binary runs.

# Strip leading env-var assignments, but only when the value doesn't
# start with `$(` or backtick — otherwise we'd chew into a command
# substitution (e.g. `URL=$(gh issue create ...)` must keep `$(gh` intact
# so the subsequent boundary class catches it). Value is restricted to
# "not whitespace and not a substitution opener", then required to end
# on whitespace so we only strip actual KEY=VAL prefixes, not KEY=VAL
# embedded mid-string.
NORMALIZED=$(echo "$COMMAND" | sed -E 's/(^|[\&\|\;\(`])[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=([^[:space:]$`]|\$[^(])*[[:space:]]+)+/\1/g')

# Boundary character class used for both start and end of an invocation
# capture. Including `)` and backtick as terminators so we don't swallow
# the rest of the outer command when inside $(…) or `…`.
GH_INVOCATIONS=$(
  echo "$NORMALIZED" \
    | grep -oE '(^|[\&\|\;\(`])[[:space:]]*gh([[:space:]][^|&;)`]*)?' \
    | sed -E 's/^[[:space:]&|;(`]*//'
)
[ -z "$GH_INVOCATIONS" ] && exit 0

# ---------- Helper: normalize argv, stripping global gh flags ----------
#
# `gh` accepts root-level flags like `-R owner/repo`, `--repo owner/repo`,
# `-H host`, `--hostname host`, `--help`, `--version` before the
# subcommand. It also accepts some of those between the subcommand and
# verb (`gh issue -R owner/repo create`). Without stripping, the simple
# positional read `gh SUB VERB …` misidentifies `SUB=-R` as a root flag
# and hits the "help/version passthrough" branch, letting ticket-create
# bypass the guard.
#
# normalize_gh_argv takes the invocation string and prints two lines:
#   SUB=<subcommand>
#   VERB=<first non-flag arg after the subcommand>
# Empty/unset SUB means pure informational (`gh --help`, `gh --version`,
# bare `gh`), which we pass through.
normalize_gh_argv() {
  # shellcheck disable=SC2206  # deliberate word-splitting of the command
  local tokens=($1)
  # Drop the leading "gh" itself.
  tokens=("${tokens[@]:1}")

  local t sub="" verb=""

  # Strip leading global flags (before the subcommand).
  while [ ${#tokens[@]} -gt 0 ]; do
    t="${tokens[0]}"
    case "$t" in
      # Informational flags — nothing to block regardless of what follows.
      --help|-h|--version|-v)
        sub=""; verb=""
        echo "SUB="
        echo "VERB="
        return 0
        ;;
      # Known gh root flags that TAKE a value.
      -R|--repo|-H|--hostname)
        tokens=("${tokens[@]:2}")
        continue
        ;;
      # --flag=value forms (single token).
      --repo=*|--hostname=*)
        tokens=("${tokens[@]:1}")
        continue
        ;;
      # Unknown leading flag — be conservative and skip just the flag
      # itself. If it takes a value and we guess wrong, worst case is
      # we still correctly extract SUB from the next positional.
      -*)
        tokens=("${tokens[@]:1}")
        continue
        ;;
      *)
        break
        ;;
    esac
  done

  [ ${#tokens[@]} -eq 0 ] && { echo "SUB="; echo "VERB="; return 0; }
  sub="${tokens[0]}"
  tokens=("${tokens[@]:1}")

  # Strip flags between the subcommand and the verb (`gh issue -R o/r create`).
  while [ ${#tokens[@]} -gt 0 ]; do
    t="${tokens[0]}"
    case "$t" in
      -R|--repo|-H|--hostname)
        tokens=("${tokens[@]:2}")
        continue
        ;;
      --repo=*|--hostname=*)
        tokens=("${tokens[@]:1}")
        continue
        ;;
      -*)
        tokens=("${tokens[@]:1}")
        continue
        ;;
      *)
        verb="$t"
        break
        ;;
    esac
  done

  echo "SUB=$sub"
  echo "VERB=$verb"
}

# ---------- Per-invocation decision ----------
while IFS= read -r INVOCATION; do
  [ -z "$INVOCATION" ] && continue

  eval "$(normalize_gh_argv "$INVOCATION")"

  # Pure informational (`gh`, `gh --help`, `gh --version`) → pass through.
  [ -z "$SUB" ] && continue

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
      # Block raw-API shortcuts that create or mutate issues/labels:
      #   gh api repos/OWNER/REPO/issues -f title=Foo              (implicit POST)
      #   gh api -X POST /repos/OWNER/REPO/issues -f title=Foo     (explicit -X space METHOD)
      #   gh api -XPOST  /repos/OWNER/REPO/issues -f title=Foo     (concatenated short flag)
      #   gh api --method POST /repos/OWNER/REPO/issues -f …       (long-form)
      #   gh api graphql -f query='mutation { issueCreate(...) }'
      #
      # Intentionally NOT blocked (these are allowed existing-resource ops):
      #   gh api -X POST /repos/…/issues/N/comments                (= gh issue comment)
      #   gh api -X PATCH /repos/…/issues/comments/ID              (edit a comment body)
      #   gh api -X POST /repos/…/issues/N/assignees               (reassign — not a ticket-create)
      #
      # The check below anchors the path regex to the collection OR single-
      # issue form (`/issues`, `/issues/N`) — NOT `/issues/N/*` — so nested
      # sub-resources fall through cleanly.

      # Detect the method. Three shapes, PLUS implicit POST when any -f/-F
      # field flag is present (per `gh api --help`: "The default HTTP method
      # for the request is GET if no parameters are set, POST otherwise.").
      METHOD=""
      # (1) -X<space>METHOD  or  --method<space>METHOD
      if echo "$INVOCATION" | grep -qE '(^|[[:space:]])(-X[[:space:]]+|--method[[:space:]]+)(POST|PATCH|PUT|DELETE)([[:space:]]|$)'; then
        METHOD=$(
          echo "$INVOCATION" \
            | grep -oE '(-X[[:space:]]+|--method[[:space:]]+)(POST|PATCH|PUT|DELETE)' \
            | head -1 \
            | grep -oE '(POST|PATCH|PUT|DELETE)'
        )
      # (2) -XPOST (concatenated, no space) — pflag short-flag convention
      elif echo "$INVOCATION" | grep -qE '(^|[[:space:]])-X(POST|PATCH|PUT|DELETE)([[:space:]]|$)'; then
        METHOD=$(
          echo "$INVOCATION" \
            | grep -oE '(^|[[:space:]])-X(POST|PATCH|PUT|DELETE)' \
            | head -1 \
            | grep -oE '(POST|PATCH|PUT|DELETE)'
        )
      # (3) --method=METHOD (long form with =)
      elif echo "$INVOCATION" | grep -qE '(^|[[:space:]])--method=(POST|PATCH|PUT|DELETE)([[:space:]]|$)'; then
        METHOD=$(
          echo "$INVOCATION" \
            | grep -oE -- '--method=(POST|PATCH|PUT|DELETE)' \
            | head -1 \
            | grep -oE '(POST|PATCH|PUT|DELETE)'
        )
      # (4) Implicit POST: any -f / -F / --field / --raw-field turns the
      #     default method from GET into POST.
      elif echo "$INVOCATION" | grep -qE '(^|[[:space:]])(-f|-F|--field|--raw-field)([[:space:]]|=)'; then
        METHOD="POST"
      fi

      if [ -n "$METHOD" ]; then
        # Path regex: ONLY the repo-scoped issues/labels collection or
        # single-resource endpoints. We anchor to `/repos/OWNER/REPO/`
        # before the collection so that nested sub-paths like
        # `/issues/42/labels`, `/issues/42/comments`, or `/issues/N/assignees`
        # do NOT accidentally match via the inner `labels` alternative —
        # the preceding segment must be the literal repo name, not
        # an issue number.
        #
        # Matches:
        #   /repos/OWNER/REPO/issues                  (collection POST → block)
        #   /repos/OWNER/REPO/issues/42               (single PATCH/DELETE → block)
        #   /repos/OWNER/REPO/labels                  (collection POST → block)
        #   /repos/OWNER/REPO/labels/chore            (single DELETE/PATCH → block)
        #   same without leading "/repos" if someone wrote "repos/…"
        # Does NOT match:
        #   /repos/OWNER/REPO/issues/42/labels        (existing-issue label mutation)
        #   /repos/OWNER/REPO/issues/42/comments      (existing-issue comment add)
        #   /repos/OWNER/REPO/issues/42/assignees     (existing-issue reassign)
        #   /repos/OWNER/REPO/issues/comments/99      (edit existing comment body)
        if echo "$INVOCATION" | grep -qE '(^|[[:space:]/])repos/[^/]+/[^/]+/(issues(/[0-9]+)?|labels(/[^/?[:space:]]+)?)(\?|[[:space:]]|$)'; then
          echo "Blocked: \`gh api\` $METHOD on a /issues or /labels collection/single-resource endpoint." >&2
          echo "" >&2
          echo "This is the raw-API equivalent of \`gh issue create\` / \`gh issue edit\`" >&2
          echo "/ \`gh label create\` / \`gh label delete\`. Ticket tracking for earthly" >&2
          echo "projects lives in Linear — use \`bender-linear-create-issue\` for creates;" >&2
          echo "leave GitHub labels alone. Read ops and nested sub-resources (e.g." >&2
          echo "\`/issues/N/comments\` for replying) remain allowed." >&2
          exit 2
        fi
      fi

      # GraphQL mutations that create/mutate issues or labels. `gh api graphql`
      # always POSTs, so we can't gate on method. Instead we match the verb
      # name in the surrounding command text.
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
