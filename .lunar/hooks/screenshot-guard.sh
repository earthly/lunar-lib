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
# Exit 0 = allow, Exit 2 = block (stderr rendered to the agent).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r ".tool_input.command // empty")
[ -z "$COMMAND" ] && exit 0

# Already routed through the validating wrapper → allow.
if echo "$COMMAND" | grep -qE '(^|[[:space:]&|;(`])bender-screenshot([[:space:]]|$)'; then
  exit 0
fi

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

# (1) Inline python with playwright + page.screenshot(
#     Match python -c "..." or python3 -c "..." OR python heredoc patterns.
#     We grep the whole COMMAND text — quoting/escaping is the agent's
#     problem; if `page.screenshot(` appears alongside `playwright`, that's
#     a screenshot call regardless of how it's wrapped.
if echo "$COMMAND" | grep -qE '(^|[[:space:]&|;(`])python3?([[:space:]]|$)' \
   && echo "$COMMAND" | grep -qE 'playwright' \
   && echo "$COMMAND" | grep -qE '\.screenshot[[:space:]]*\('; then
  emit_block "inline Python with \`page.screenshot(...)\` (Playwright)"
fi

# (2) `playwright` CLI with the `screenshot` verb
#     `playwright screenshot URL output.png` is the documented invocation.
if echo "$COMMAND" | grep -qE '(^|[[:space:]&|;(`])playwright[[:space:]]+screenshot([[:space:]]|$)'; then
  emit_block "\`playwright screenshot\` CLI"
fi

# (3) Headless Chromium with --screenshot= flag
if echo "$COMMAND" | grep -qE '(^|[[:space:]&|;(`])(chromium|chrome|google-chrome|chromium-browser)([[:space:]][^|&;)`]*)?--screenshot(=|[[:space:]])'; then
  emit_block "headless Chromium \`--screenshot=\` flag"
fi

exit 0
