#!/bin/bash
# screenshot-guard.sh — agent-before-command hook for screenshot-taking commands.
#
# Forces all PR-evidence screenshots through `bender-screenshot`, which refuses
# to save a PNG unless every string in `must_be_visible` is actually inside the
# final viewport. The legacy nudge-only `screenshot-quality-reminder` was
# repeatedly ignored — agents would post top-of-page screenshots that hid the
# data the reviewer needed (PR #142 trigger).
#
# Detects raw screenshot calls in three shapes and blocks them:
#   1. Inline Python that imports playwright + calls page.screenshot(...)
#   2. `playwright` CLI with `screenshot` verb
#   3. Headless Chromium (`chromium`, `chrome`, `google-chrome`) with --screenshot=
#
# Allowed (exits 0): `bender-screenshot --spec ...` and any non-screenshot use
# of python/playwright/chromium. The matcher is intentionally narrow — running
# a Playwright test suite or unrelated Python code is fine.
#
# Decisions are made per-invocation (each `&&`/`||`/`;`/`|`-separated segment
# in the command), modelled on the sibling `gh-issue-guard.sh`. That way a
# benign `bender-screenshot --help` cannot be chained to whitelist a follow-on
# raw screenshot call (PR #153 review feedback).
#
# Exit 0 = allow, Exit 2 = block (stderr rendered to the agent).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r ".tool_input.command // empty")
[ -z "$COMMAND" ] && exit 0

emit_block() {
  local kind="$1"
  echo "Blocked: $kind." >&2
  echo "" >&2
  echo "PR-evidence screenshots must go through \`bender-screenshot\`, which" >&2
  echo "refuses to save unless every string in \`must_be_visible\` is actually" >&2
  echo "inside the final viewport. Top-of-page screenshots that hide the" >&2
  echo "tested data have been a recurring PR-review failure (see #142)." >&2
  echo "" >&2
  echo "Use:" >&2
  echo "" >&2
  echo "  bender-screenshot --spec - <<EOF" >&2
  echo "  {" >&2
  echo "    \"preset\": \"cronos\"," >&2
  echo "    \"url\": \"https://cronos.demo.earthly.dev/d/...\"," >&2
  echo "    \"scroll_to_text\": \"<row or key the screenshot must land on>\"," >&2
  echo "    \"must_be_visible\": [\"<strings reviewer must see>\"]," >&2
  echo "    \"output\": \"/tmp/<name>.png\"" >&2
  echo "  }" >&2
  echo "  EOF" >&2
  echo "" >&2
  echo "If \`scroll_to_text\` is in a virtualized table (Grafana checks panel)," >&2
  echo "the wrapper will scroll the grid container until the row materializes." >&2
  echo "If the screenshot legitimately doesn't need validation (e.g. a local" >&2
  echo "debug capture you won't post to a PR), drop the file under /tmp and" >&2
  echo "don't upload it — this guard only fires on screenshot-taking commands," >&2
  echo "not on file moves." >&2
  exit 2
}

# ---------- Strip leading env-var assignments per segment ----------
# Same approach as gh-issue-guard.sh: an LLM could otherwise bypass with
# `FOO=1 chromium --screenshot=...`. KEY=VAL prefixes only affect the
# child process's env, not whether the binary runs.
NORMALIZED=$(echo "$COMMAND" | sed -E 's/(^|[\&\|\;\(`])[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=([^[:space:]$`]|\$[^(])*[[:space:]]+)+/\1/g')

# ---------- Capture each invocation of a binary we care about ----------
# Boundary class includes `/` so path-prefixed binaries (`/usr/bin/python`)
# anchor correctly. Optional path prefix `([^[:space:]&|;()`]*/)?` matches
# any directory components before the basename. Python binary alternation
# accepts versioned names (`python3.11`, `python3.10`, `python`) via
# `python([0-9]+(\.[0-9]+)*)?`. Trailing args group greedy-matches up to
# the next shell separator.
INVOCATIONS=$(
  echo "$NORMALIZED" \
    | grep -oE '(^|[\&\|\;\(`])[[:space:]]*([^[:space:]&|;()`]*/)?(python([0-9]+(\.[0-9]+)*)?|playwright|chromium-browser|chromium|google-chrome|chrome|bender-screenshot)([[:space:]][^|&;)`]*)?' \
    | sed -E 's/^[[:space:]&|;(`]*//'
)
[ -z "$INVOCATIONS" ] && exit 0

# ---------- Per-invocation decision ----------
while IFS= read -r INVOCATION; do
  [ -z "$INVOCATION" ] && continue

  # First token is the binary (with optional path prefix).
  FIRST_TOKEN=$(echo "$INVOCATION" | awk '{print $1}')
  BIN=$(basename -- "$FIRST_TOKEN" 2>/dev/null)
  [ -z "$BIN" ] && continue

  case "$BIN" in
    bender-screenshot)
      # Already routed through the validating wrapper — pass this invocation.
      continue
      ;;

    python|python[0-9]*)
      # (1) Inline python with playwright + page.screenshot(
      # We grep the WHOLE COMMAND text — quoting/escaping is the agent's
      # problem; if `page.screenshot(` appears alongside `playwright`, that's
      # a screenshot call regardless of how it's wrapped.
      if echo "$COMMAND" | grep -qE 'playwright' \
         && echo "$COMMAND" | grep -qE '\.screenshot[[:space:]]*\('; then
        emit_block "inline Python with \`page.screenshot(...)\` (Playwright)"
      fi
      ;;

    playwright)
      # (2) `playwright screenshot URL output.png`
      VERB=$(echo "$INVOCATION" | awk '{print $2}')
      if [ "$VERB" = "screenshot" ]; then
        emit_block "\`playwright screenshot\` CLI"
      fi
      ;;

    chromium|chromium-browser|chrome|google-chrome)
      # (3) Headless Chromium with --screenshot flag.
      # Tokenize on whitespace (shell word-splitting) and check whether
      # any token equals `--screenshot` or starts with `--screenshot=`.
      # This avoids false-positives on URLs whose query strings happen to
      # contain the literal substring `--screenshot=` (PR #153 review).
      # shellcheck disable=SC2086  # deliberate word-splitting of the invocation
      set -- $INVOCATION
      shift  # drop the binary itself
      for tok in "$@"; do
        # Strip surrounding single/double quotes if any.
        clean="${tok#\"}"; clean="${clean%\"}"
        clean="${clean#\'}"; clean="${clean%\'}"
        case "$clean" in
          --screenshot|--screenshot=*)
            emit_block "headless Chromium \`--screenshot=\` flag"
            ;;
        esac
      done
      ;;
  esac
done <<< "$INVOCATIONS"

exit 0
