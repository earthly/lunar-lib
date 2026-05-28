#!/bin/sh
# scripts/check-pr-title.sh
#
# Shared check for the block + warn probes in lunar-probe.yml.
# Stdin:  PreToolUse JSON payload from lunar-probe.
# Stdout: the offending title (on block) — surfaced via {check_stdout}.
# Exit:   0 = allow (skip-safe), 1 = block.

set -u

cmd="$(jq -r '.tool_input.command // ""' 2>/dev/null || printf '')"
[ -z "$cmd" ] && exit 0

# Defer to gh when the title is built via shell substitution — we
# can't see the post-expansion value, so blocking risks false
# positives (e.g. `--title "[ENG-$(num)] foo"`).
case "$cmd" in
    *'`'*|*'$('*) exit 0 ;;
esac

# Tokenize via xargs — quote-aware, doesn't expand $VAR and doesn't
# apply redirections, so we can inspect commands without side effects.
tokens="$(printf '%s\n' "$cmd" | xargs -n1 2>/dev/null)" || exit 0
[ -z "$tokens" ] && exit 0

OLD_IFS="$IFS"
IFS='
'
# shellcheck disable=SC2086
set -- $tokens
IFS="$OLD_IFS"

# Must be `gh ... pr create` (allow leading flags before the subcommand).
[ "${1:-}" = "gh" ] || exit 0
shift
while [ $# -gt 0 ]; do
    case "$1" in
        --*=*|--*|-*) shift ;;
        *) break ;;
    esac
done
[ "${1:-}" = "pr" ] || exit 0
shift
[ "${1:-}" = "create" ] || exit 0
shift

title=""
draft=0
while [ $# -gt 0 ]; do
    case "$1" in
        --draft|-d) draft=1; shift ;;
        --title)    shift; title="${1:-}"; [ $# -gt 0 ] && shift ;;
        --title=*)  title="${1#--title=}"; shift ;;
        -t)         shift; title="${1:-}"; [ $# -gt 0 ] && shift ;;
        -t?*)       title="${1#-t}"; shift ;;
        *)          shift ;;
    esac
done

[ "$draft" -eq 1 ] && exit 0

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || printf '')"
case "$branch" in
    dependabot/*|renovate/*) exit 0 ;;
esac

[ -z "$title" ] && exit 0

case "$(printf '%s' "$title" | tr '[:upper:]' '[:lower:]')" in
    no-ticket:*) exit 0 ;;
esac

# Translate PCRE \d → POSIX ERE [0-9] for grep -E portability.
pattern="${LUNAR_VAR_PATTERN:-[A-Z]+-\\d+}"
pattern_ere="$(printf '%s' "$pattern" | sed 's/\\d/[0-9]/g')"

if printf '%s' "$title" | grep -qE "$pattern_ere"; then
    exit 0
fi

printf '%s' "$title"
exit 1
