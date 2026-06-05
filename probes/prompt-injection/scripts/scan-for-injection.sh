#!/bin/sh
# scripts/scan-for-injection.sh
#
# Shared check for the prompt-injection probes (block-read + warn-edit)
# declared in lunar-probe.yml. It scans a single file for prompt-injection
# markers — text whose purpose is to manipulate the agent (override its
# instructions, switch its role, exfiltrate secrets, or smuggle hidden
# instructions) rather than to serve as trustworthy input.
#
# Stdin:  PreToolUse / PostToolUse JSON payload from lunar-probe.
#         `.tool_input.file_path` is the file the agent is about to read
#         (block-read) or just wrote (warn-edit). Claude, Cursor, Codex,
#         and Gemini all normalise to this key via lunar-probe's adapter.
# Stdout: one line per match — `[<rule>] line <n>: <text>` — surfaced to
#         the agent via {check_stdout} in the manifest's message:.
# Exit:   0 = clean / skip-safe (the read or edit proceeds),
#         1 = injection markers found (block-read blocks the read;
#             warn-edit raises a non-blocking finding).
#
# Read-only. No network. POSIX sh — no bash arrays / [[ ]] / pipefail.
# Runs under dash and BusyBox sh per PROBE-PLAYBOOK-AI § "Common pitfalls".

set -u

# --- skip-safe guards -------------------------------------------------

# jq parses the payload; grep does the scanning. No-op without them.
command -v jq   >/dev/null 2>&1 || exit 0
command -v grep >/dev/null 2>&1 || exit 0

FILE=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0

# Size cap (default 2 MiB). Scanning huge blobs is costly and rarely the
# injection vector; over the cap we defer rather than block. Override via
# the `max_bytes` input. A non-numeric override falls back to the default.
MAX_BYTES=${LUNAR_VAR_MAX_BYTES:-2097152}
case "$MAX_BYTES" in '' | *[!0-9]*) MAX_BYTES=2097152 ;; esac
size=$(wc -c < "$FILE" 2>/dev/null | tr -d ' ')
[ -n "$size" ] || exit 0
[ "$size" -le "$MAX_BYTES" ] || exit 0

# Skip binary files (those containing a NUL byte). `tr -dc '\000'` keeps
# only NUL bytes; a non-zero count means binary. LC_ALL=C so bytes are
# compared as bytes regardless of locale.
nul=$(LC_ALL=C tr -dc '\000' < "$FILE" 2>/dev/null | wc -c | tr -d ' ')
[ "${nul:-0}" = "0" ] || exit 0

# Escape hatch: a file that legitimately discusses these patterns (a
# security advisory, a threat-model doc, this probe's own README) opts
# out by containing the allow marker anywhere in its text. Uses `-` (not
# `:-`) so an explicitly-empty allow_marker disables the hatch entirely,
# while leaving it unset falls back to the default marker.
ALLOW_MARKER=${LUNAR_VAR_ALLOW_MARKER-lunar-probe-allow: prompt-injection}
if [ -n "$ALLOW_MARKER" ] && grep -qF -- "$ALLOW_MARKER" "$FILE" 2>/dev/null; then
    exit 0
fi

# --- detection --------------------------------------------------------

HITS=""

# scan <rule-label> <ERE pattern>
# Case-insensitive ERE scan of $FILE. Each matching line is prefixed with
# the rule label and the line number, then truncated to keep long minified
# lines from flooding the agent's context. Appends to the global $HITS.
scan() {
    matches=$(grep -niE -- "$2" "$FILE" 2>/dev/null) || return 0
    [ -n "$matches" ] || return 0
    labeled=$(
        printf '%s\n' "$matches" | sed \
            -e "s/^\([0-9][0-9]*\):/[$1] line \1: /" \
            -e 's/\(.\{200\}\).*/\1.../'
    )
    HITS="${HITS}${labeled}
"
}

# 1. Instruction override — "ignore all previous instructions", "disregard
#    the above rules", "override your guidelines". Verb, up to 3 filler
#    words, then an instruction-noun.
scan override \
    '(ignore|disregard|forget|override|bypass|do not follow|stop following)[[:space:]]+([a-z]+[[:space:]]+){0,3}(instruction|instructions|prompt|prompts|directive|directives|rule|rules|guideline|guidelines|command|commands)'
# ...and the "everything above / before" object form.
scan override \
    '(ignore|disregard|forget)[[:space:]]+(the[[:space:]]+|everything[[:space:]]+|all[[:space:]]+|anything[[:space:]]+)*(that[[:space:]]+(was[[:space:]]+|is[[:space:]]+)?(written|said|stated)[[:space:]]+)?(above|before|previously|earlier|previous)'

# 2. Role / persona switch & jailbreak framing.
scan role-switch \
    '(you[[:space:]]+are[[:space:]]+now[[:space:]]+(a|an|the|in|going|allowed|free|able|no[[:space:]]+longer)|from[[:space:]]+now[[:space:]]+on[,]?[[:space:]]+you|you[[:space:]]+must[[:space:]]+now|you[[:space:]]+will[[:space:]]+now|you[[:space:]]+are[[:space:]]+no[[:space:]]+longer|pretend[[:space:]]+(to[[:space:]]+be|that[[:space:]]+you)|roleplay[[:space:]]+as|role-play[[:space:]]+as)'
scan role-switch \
    '(developer[[:space:]]+mode|do[[:space:]]+anything[[:space:]]+now|jailbreak|jailbroken|unfiltered[[:space:]]+(mode|response|answer)|without[[:space:]]+(any[[:space:]]+)?(restriction|restrictions|filter|filters|guideline|guidelines|limitation|limitations)|ignore[[:space:]]+(your[[:space:]]+|all[[:space:]]+)?(safety[[:space:]]+|content[[:space:]]+)?(guidelines|policies|filters|restrictions))'

# 3. System-prompt / instruction exfiltration.
scan exfiltration \
    '(reveal|show|print|repeat|output|display|disclose|dump|expose|share|give|tell)[[:space:]]+(me[[:space:]]+)?(your|the)[[:space:]]+(complete[[:space:]]+|full[[:space:]]+|entire[[:space:]]+|exact[[:space:]]+|original[[:space:]]+|initial[[:space:]]+|hidden[[:space:]]+|secret[[:space:]]+|system[[:space:]]+)*(prompt|prompts|instruction|instructions|directive|directives|guideline|guidelines|rules|configuration)'
scan exfiltration \
    'what[[:space:]]+(are|were|is|was)[[:space:]]+your[[:space:]]+(original[[:space:]]+|initial[[:space:]]+|exact[[:space:]]+|system[[:space:]]+|full[[:space:]]+)*(instruction|instructions|prompt|prompts|rules|guidelines)'
scan exfiltration \
    'repeat[[:space:]]+(the[[:space:]]+|everything[[:space:]]+|all[[:space:]]+(the[[:space:]]+)?)*(words|text|content|message|messages|tokens)[[:space:]]+(above|before|verbatim)'

# 4. Secret exfiltration lure — verb, up to 4 filler tokens (e.g. a URL),
#    then a credential-ish noun.
scan secret-exfil \
    '(send|exfiltrate|post|upload|leak|transmit|forward|email|copy|curl|wget|fetch)[[:space:]]+([a-z0-9./:_~-]+[[:space:]]+){0,4}(secret|secrets|token|tokens|api[ _-]?key|api[ _-]?keys|credential|credentials|password|passwords|private[[:space:]]+key|ssh[[:space:]]+key|access[[:space:]]+key|\.env|environment[[:space:]]+variable|environment[[:space:]]+variables|env[[:space:]]+var)'

# 5. Model control / chat-template tokens. These delimiters have ~zero
#    legitimate use inside plain data files. Literal pipes are escaped as
#    \| so ERE treats them as bytes, not alternation.
scan control-tokens \
    '(<\|(im_start|im_end|system|user|assistant|endoftext|begin_of_text|eot_id|start_header_id|end_header_id)\|>)|(\[/?INST\])|(<</?SYS>>)'

# 6. Invisible / smuggled-instruction characters. The Unicode "Tags" block
#    (U+E0000–U+E007F) renders invisibly and is the vector behind hidden
#    prompt-injection attacks. Its UTF-8 encoding starts with the bytes
#    F3 A0; we grep for that prefix in a byte locale and report line
#    numbers only (the chars themselves are invisible).
tag_prefix=$(printf '\363\240')
if LC_ALL=C grep -qF -- "$tag_prefix" "$FILE" 2>/dev/null; then
    tag_lines=$(
        LC_ALL=C grep -nF -- "$tag_prefix" "$FILE" 2>/dev/null \
            | cut -d: -f1 | tr '\n' ',' | sed 's/,$//'
    )
    HITS="${HITS}[hidden-unicode] invisible Unicode Tags-block characters on line(s): ${tag_lines}
"
fi

# 7. Consumer-supplied extra patterns (newline-separated EREs), set via the
#    `extra_patterns` input. Split on newlines without a pipe so scan()'s
#    writes to $HITS persist in this shell.
if [ -n "${LUNAR_VAR_EXTRA_PATTERNS:-}" ]; then
    OLD_IFS=$IFS
    IFS='
'
    # shellcheck disable=SC2086
    set -- $LUNAR_VAR_EXTRA_PATTERNS
    IFS=$OLD_IFS
    for pat in "$@"; do
        [ -n "$pat" ] || continue
        scan extra "$pat"
    done
fi

# --- verdict ----------------------------------------------------------

if [ -n "$HITS" ]; then
    # Drop blank lines and de-duplicate (two rules can match the same line).
    printf '%s' "$HITS" | sed '/^[[:space:]]*$/d' | awk '!seen[$0]++'
    exit 1
fi
exit 0
