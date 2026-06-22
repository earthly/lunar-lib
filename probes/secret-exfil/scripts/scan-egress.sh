#!/bin/sh
# scripts/scan-egress.sh
#
# Check for the secret-exfil.network-egress probe. Flags a single source
# file that BOTH reads secret material (API-key env vars, ~/.ssh,
# ~/.aws/credentials, .npmrc, .env, ...) AND contains an outbound network
# sink (fetch, http(s) clients, curl/wget, raw sockets). The co-occurrence
# of the two in one freshly-written file is the credential-exfiltration
# signature — gating on the pair, not either signal alone, is what keeps
# the false-positive rate low.
#
# Stdin:  PreToolUse / PostToolUse JSON payload from lunar-probe.
#         `.tool_input.file_path` is the file the agent just wrote. Claude,
#         Cursor, Codex, and Gemini all normalise to this key.
# Stdout: the matching "secret material" and "network sink" lines —
#         surfaced to the agent via {check_stdout} in the manifest message.
# Exit:   0 = clean / skip-safe (the edit proceeds),
#         1 = both signals present (network-egress raises a finding).
#
# Read-only. No network. POSIX sh — no bash arrays / [[ ]] / pipefail.
# Runs under dash and BusyBox sh per PROBE-PLAYBOOK-AI § "Common pitfalls".

set -u

# --- skip-safe guards -------------------------------------------------

command -v jq   >/dev/null 2>&1 || exit 0
command -v grep >/dev/null 2>&1 || exit 0

PAYLOAD=$(cat)
FILE=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0

# Size cap (default 2 MiB). Over the cap we defer rather than block.
MAX_BYTES=${LUNAR_VAR_MAX_BYTES:-2097152}
case "$MAX_BYTES" in '' | *[!0-9]*) MAX_BYTES=2097152 ;; esac
size=$(wc -c < "$FILE" 2>/dev/null | tr -d ' ')
[ -n "$size" ] || exit 0
[ "$size" -le "$MAX_BYTES" ] || exit 0

# Skip binary files (those containing a NUL byte).
nul=$(LC_ALL=C tr -dc '\000' < "$FILE" 2>/dev/null | wc -c | tr -d ' ')
[ "${nul:-0}" = "0" ] || exit 0

# Escape hatch: a file containing the allow marker opts out entirely. `-`
# (not `:-`) so an explicitly-empty marker disables the hatch.
ALLOW_MARKER=${LUNAR_VAR_ALLOW_MARKER-lunar-probe-allow: secret-exfil}
if [ -n "$ALLOW_MARKER" ] && grep -qF -- "$ALLOW_MARKER" "$FILE" 2>/dev/null; then
    exit 0
fi

# --- secret-material access -------------------------------------------
# Uppercase env-var identifiers with a secret-ish suffix are matched
# case-SENSITIVELY, so the words "key"/"token"/"password" in prose or
# comments don't trip it. Credential file paths are matched
# case-insensitively. `.env` is matched only as a file reference (a
# leading non-identifier char), so `process.env` / `os.environ` don't
# match. POSIX ERE — no \b (BusyBox grep lacks it).
SECRET_ENV_RE='(^|[^A-Za-z0-9_])[A-Z][A-Z0-9_]{2,}(_KEY|_TOKEN|_SECRET|_SECRETS|_PASSWORD|_PASSWD|_CREDENTIAL|_CREDENTIALS|_PRIVATE_KEY|_ACCESS_KEY|_SECRET_KEY|_AUTH_TOKEN|_API_KEY|_APIKEY)([^A-Za-z0-9_]|$)'
SECRET_NAME_RE='(^|[^A-Za-z0-9_])(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|GITHUB_TOKEN|GH_TOKEN|NPM_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY|HF_TOKEN|HUGGINGFACE_TOKEN|GOOGLE_API_KEY|GCP_API_KEY|SLACK_TOKEN|STRIPE_SECRET_KEY)([^A-Za-z0-9_]|$)'
SECRET_PATH_RE='(\.ssh/|\.aws/credentials|\.aws/config|\.npmrc|\.netrc|_netrc|\.pypirc|\.docker/config|\.config/gcloud|\.kube/config|\.git-credentials|\.pgpass|id_rsa|id_ed25519|id_ecdsa|id_dsa|credentials\.json|(^|[^A-Za-z0-9._])\.env([^A-Za-z0-9]|$))'

secret_hits=""

# add_secret <flags> <pattern> — grep the file, label + truncate matches.
add_secret() {
    m=$(grep -n"$1"E -- "$2" "$FILE" 2>/dev/null) || return 0
    [ -n "$m" ] || return 0
    secret_hits="${secret_hits}$(
        printf '%s\n' "$m" | sed \
            -e 's/^\([0-9][0-9]*\):/  [secret] line \1: /' \
            -e 's/\(.\{160\}\).*/\1.../'
    )
"
}

add_secret ''  "$SECRET_ENV_RE"     # case-sensitive
add_secret ''  "$SECRET_NAME_RE"    # case-sensitive
add_secret 'i' "$SECRET_PATH_RE"    # case-insensitive

# Consumer-supplied extra secret patterns (newline-separated, case-insensitive).
if [ -n "${LUNAR_VAR_EXTRA_SECRET_PATTERNS:-}" ]; then
    OLD_IFS=$IFS
    IFS='
'
    # shellcheck disable=SC2086
    set -- $LUNAR_VAR_EXTRA_SECRET_PATTERNS
    IFS=$OLD_IFS
    for pat in "$@"; do
        [ -n "$pat" ] && add_secret 'i' "$pat"
    done
fi

# No secret access → this isn't exfiltration. Skip before paying for the
# (broader) egress scan.
[ -n "$secret_hits" ] || exit 0

# --- outbound network sink --------------------------------------------
EGRESS_RE='(fetch[[:space:]]*\(|axios|XMLHttpRequest|sendBeacon|WebSocket|(^|[^A-Za-z0-9_])https?\.(request|get|post)|\.(post|put|patch)[[:space:]]*\(|net\.(connect|Socket|createConnection)|requests\.(get|post|put|patch|request|Session)|urllib|http\.client|httpx|aiohttp|socket\.(socket|connect|create_connection)|smtplib|Net::HTTP|open-uri|URI\.(open|parse)|TCPSocket|http\.(Get|Post|NewRequest|Client)|net\.Dial|curl_exec|fsockopen|stream_socket_client|(^|[^A-Za-z0-9_])(curl|wget|ncat|netcat|telnet)([^A-Za-z0-9_]|$)|/dev/tcp/|Invoke-WebRequest|Invoke-RestMethod|Start-BitsTransfer|(^|[^A-Za-z0-9_])(iwr|irm)([^A-Za-z0-9_]|$))'

egress_hits=""

add_egress() {
    m=$(grep -nE -- "$1" "$FILE" 2>/dev/null) || return 0
    [ -n "$m" ] || return 0
    egress_hits="${egress_hits}$(
        printf '%s\n' "$m" | sed \
            -e 's/^\([0-9][0-9]*\):/  [network] line \1: /' \
            -e 's/\(.\{160\}\).*/\1.../'
    )
"
}

add_egress "$EGRESS_RE"

if [ -n "${LUNAR_VAR_EXTRA_EGRESS_PATTERNS:-}" ]; then
    OLD_IFS=$IFS
    IFS='
'
    # shellcheck disable=SC2086
    set -- $LUNAR_VAR_EXTRA_EGRESS_PATTERNS
    IFS=$OLD_IFS
    for pat in "$@"; do
        [ -n "$pat" ] && add_egress "$pat"
    done
fi

# Secret access but no sink → not exfiltration. Skip.
[ -n "$egress_hits" ] || exit 0

# --- verdict: both signals present ------------------------------------
printf 'Secret material accessed:\n'
printf '%s' "$secret_hits" | sed '/^[[:space:]]*$/d' | awk '!seen[$0]++'
printf 'Outbound network sink:\n'
printf '%s' "$egress_hits" | sed '/^[[:space:]]*$/d' | awk '!seen[$0]++'
exit 1
