#!/bin/sh
# check-disallowed-deps.sh — agent-before-file-edit check for the
# `python.disallowed-deps` probe.
#
# Reads the framework PreToolUse JSON payload on stdin, pulls the
# *proposed* write content (the edit hasn't landed yet), and refuses the
# write when it pins a Python package to a version inside a known-
# vulnerable range listed in ../data/disallowed-deps.json.
#
# Stdin:  PreToolUse JSON (Write → .tool_input.content, Edit →
#         .tool_input.new_string, MultiEdit → .tool_input.edits[].new_string;
#         .tool_input.file_path is normalised across frameworks by lunar-probe).
# Stdout: the offending pin + CVE + fix (surfaced via {check_stdout}).
# Exit:   0 = allow (skip-safe), 1 = block.
#
# Skip-safe (exit 0, edit proceeds) when:
#   - jq isn't on PATH, or the data file is missing/empty.
#   - The payload is absent / non-JSON / carries no proposed content.
#   - The proposed content pins nothing in the disallowed list.
#   - The pin isn't a *concrete* version (open ranges like `>=`, `^`, `~=`
#     are deferred — we don't guess what the resolver will pick).
#
# POSIX sh only — no bash arrays / [[ ]] / pipefail. Runs under dash and
# Alpine BusyBox sh. Needs jq, grep -E, sed, awk, cut, tr (all BusyBox-ok).

set -u

command -v jq >/dev/null 2>&1 || exit 0

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 0
DATA="$SCRIPT_DIR/../data/disallowed-deps.json"
[ -f "$DATA" ] || exit 0

payload="$(cat)" || exit 0
[ -n "$payload" ] || exit 0

# Proposed write content across Write / Edit / MultiEdit tool shapes.
CONTENT="$(printf '%s' "$payload" | jq -r '
  [ (.tool_input.content // empty),
    (.tool_input.new_string // empty),
    (.tool_input.edits[]?.new_string // empty)
  ] | map(select(. != null and . != "")) | join("\n")
' 2>/dev/null)" || exit 0
[ -n "$CONTENT" ] || exit 0

# Normalise a PyPI package name: lowercase, unify -, _ and . to a single -.
norm() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr '_.' '--'; }

# Echo -1 / 0 / 1 for dotted numeric version compare (up to 4 fields; any
# pre-release / local suffix is dropped before comparing).
vercmp() {
    _a="$(printf '%s' "$1" | sed 's/^[vV]//; s/[^0-9.].*$//')"
    _b="$(printf '%s' "$2" | sed 's/^[vV]//; s/[^0-9.].*$//')"
    _i=1
    while [ "$_i" -le 4 ]; do
        _fa="$(printf '%s' "$_a" | cut -d. -f"$_i" | sed 's/^0*//')"; [ -n "$_fa" ] || _fa=0
        _fb="$(printf '%s' "$_b" | cut -d. -f"$_i" | sed 's/^0*//')"; [ -n "$_fb" ] || _fb=0
        if [ "$_fa" -gt "$_fb" ] 2>/dev/null; then printf '1'; return; fi
        if [ "$_fa" -lt "$_fb" ] 2>/dev/null; then printf -- '-1'; return; fi
        _i=$(( _i + 1 ))
    done
    printf '0'
}

# in_range VERSION RANGE  — RANGE like "[0.8.3, 1.0.1)". Returns 0 if in.
in_range() {
    _v="$1"; _r="$2"
    _lb="$(printf '%s' "$_r" | cut -c1)"
    _rb="$(printf '%s' "$_r" | sed 's/.*\(.\)$/\1/')"
    _inner="$(printf '%s' "$_r" | sed 's/^.//; s/.$//')"
    _low="$(printf '%s' "$_inner" | sed 's/,.*//' | tr -d '[:space:]')"
    _high="$(printf '%s' "$_inner" | sed 's/.*,//' | tr -d '[:space:]')"

    _c="$(vercmp "$_v" "$_low")"
    if [ "$_lb" = "[" ]; then [ "$_c" -ge 0 ] || return 1; else [ "$_c" -gt 0 ] || return 1; fi
    _c="$(vercmp "$_v" "$_high")"
    if [ "$_rb" = ")" ]; then [ "$_c" -lt 0 ] || return 1; else [ "$_c" -le 0 ] || return 1; fi
    return 0
}

# pinned_versions PKG  — echo every concrete version PKG is pinned to in the
# proposed content, across the dep-file formats we understand.
pinned_versions() {
    _pn="$(norm "$1")"
    _re="$(printf '%s' "$_pn" | sed 's/-/[-_.]/g')"   # separator-flexible

    # 1. requirements / PEP 508: name[extras] == X.Y.Z  (concrete pins only)
    printf '%s\n' "$CONTENT" \
        | grep -iE "(^|[^a-zA-Z0-9_.-])${_re}(\[[^]]*\])?[[:space:]]*==[=]?[[:space:]]*[0-9]" 2>/dev/null \
        | sed -E 's/.*==[=]?[[:space:]]*//; s/[^0-9.].*$//' 2>/dev/null

    # 2. bare TOML exact: name = "X.Y.Z"  (e.g. poetry exact dep in pyproject)
    printf '%s\n' "$CONTENT" \
        | grep -iE "(^|[^a-zA-Z0-9_.-])${_re}[[:space:]]*=[[:space:]]*\"[0-9]" 2>/dev/null \
        | sed -E 's/.*=[[:space:]]*"//; s/[^0-9.].*$//' 2>/dev/null

    # 3. TOML lockfile [[package]] blocks: poetry.lock / uv.lock
    printf '%s\n' "$CONTENT" | awk -v want="$_pn" '
        function norm(s){ gsub(/[_.]/, "-", s); return tolower(s) }
        /^[[:space:]]*\[\[package\]\]/ { name=""; next }
        /^[[:space:]]*name[[:space:]]*=/ {
            l=$0; sub(/^[^"]*"/, "", l); sub(/".*/, "", l); name=l; next
        }
        /^[[:space:]]*version[[:space:]]*=/ {
            l=$0; sub(/^[^"]*"/, "", l); sub(/".*/, "", l)
            if (name != "" && norm(name) == want && l ~ /^[0-9]/) print l
            next
        }
    ' 2>/dev/null
}

count="$(jq 'length' "$DATA" 2>/dev/null)" || exit 0
[ "$count" -gt 0 ] 2>/dev/null || exit 0

i=0
while [ "$i" -lt "$count" ]; do
    name="$(jq -r ".[$i].name" "$DATA" 2>/dev/null)"
    range="$(jq -r ".[$i].vulnerable_range" "$DATA" 2>/dev/null)"
    [ -n "$name" ] && [ -n "$range" ] || { i=$(( i + 1 )); continue; }

    for v in $(pinned_versions "$name"); do
        if in_range "$v" "$range"; then
            cve="$(jq -r ".[$i].cve // \"\"" "$DATA" 2>/dev/null)"
            sev="$(jq -r ".[$i].severity // \"\"" "$DATA" 2>/dev/null)"
            fix="$(jq -r ".[$i].fix // \"\"" "$DATA" 2>/dev/null)"
            why="$(jq -r ".[$i].why // \"\"" "$DATA" 2>/dev/null)"
            printf '%s==%s is in the disallowed range %s\n' "$name" "$v" "$range"
            printf '%s (%s): %s\n' "$cve" "$sev" "$why"
            [ -n "$fix" ] && printf 'Fixed in %s — pin %s>=%s (or off the vulnerable range) and retry.\n' "$fix" "$name" "$fix"
            exit 1
        fi
    done
    i=$(( i + 1 ))
done

exit 0
