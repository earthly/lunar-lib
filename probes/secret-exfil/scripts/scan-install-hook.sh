#!/bin/sh
# scripts/scan-install-hook.sh
#
# Check for the secret-exfil.install-hook probe. Parses a package.json and
# flags npm lifecycle install hooks (preinstall / install / postinstall /
# prepare) whose body fetch-and-executes remote code, runs an obfuscated
# payload, opens a reverse shell, or touches credential paths — the npm
# supply-chain remote-code-execution vector. These scripts run
# automatically on `npm install`, with no prompt.
#
# Flags the DANGEROUS BODY, not the mere presence of a hook, so legitimate
# build hooks (`node scripts/build.js`, `husky install`, `prisma generate`,
# node-gyp / prebuild-install binary fetches) do not trip it.
#
# Stdin:  lunar-probe PreToolUse/PostToolUse JSON; `.tool_input.file_path`.
# Stdout: one line per dangerous hook — `[<hook>] <body>`.
# Exit:   0 = clean / skip-safe (the edit proceeds),
#         1 = a dangerous install hook was found.
#
# Read-only. No network. POSIX sh — no bash arrays / [[ ]] / pipefail.

set -u

# --- skip-safe guards -------------------------------------------------

command -v jq   >/dev/null 2>&1 || exit 0
command -v grep >/dev/null 2>&1 || exit 0

PAYLOAD=$(cat)
FILE=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0

# Only inspect package.json (paths: already filters this, but be defensive).
case "$(basename "$FILE")" in
    package.json) ;;
    *) exit 0 ;;
esac

MAX_BYTES=${LUNAR_VAR_MAX_BYTES:-2097152}
case "$MAX_BYTES" in '' | *[!0-9]*) MAX_BYTES=2097152 ;; esac
size=$(wc -c < "$FILE" 2>/dev/null | tr -d ' ')
[ -n "$size" ] || exit 0
[ "$size" -le "$MAX_BYTES" ] || exit 0

ALLOW_MARKER=${LUNAR_VAR_ALLOW_MARKER-lunar-probe-allow: secret-exfil}
if [ -n "$ALLOW_MARKER" ] && grep -qF -- "$ALLOW_MARKER" "$FILE" 2>/dev/null; then
    exit 0
fi

# --- dangerous-body signatures ----------------------------------------
# Fetch-and-execute, dynamic exec, decode-to-shell, reverse shell, and
# credential access. Case-insensitive. POSIX ERE — no \b.
DANGER_RE='((curl|wget|fetch)[^|&;]*(\||&&|;|`|\$\()[[:space:]]*(sh|bash|zsh|node|python3?|ruby|perl)|(^|[^A-Za-z0-9_])(sh|bash|zsh)[[:space:]]+-c([[:space:]]|$)|node[[:space:]]+(-e|--eval)|python3?[[:space:]]+-c|(^|[^A-Za-z0-9_])eval([[:space:]]*\(|[[:space:]])|Function[[:space:]]*\(|atob[[:space:]]*\(|base64[[:space:]]+(-d|--decode|-D)|/dev/tcp/|(^|[^A-Za-z0-9_])nc[[:space:]]+-e|bash[[:space:]]+-i|Invoke-Expression|Invoke-WebRequest|Start-BitsTransfer|(^|[^A-Za-z0-9_])(iex|iwr)([^A-Za-z0-9_]|$)|printenv|(^|[^A-Za-z0-9_])env[[:space:]]*\||\.ssh/|\.aws/credentials|(^|[^A-Za-z0-9_])\.npmrc)'

hits=""

# jq extracts each hook body directly — no tab parsing. Invalid JSON makes
# every lookup empty, so a non-JSON file is skip-safe (exit 0).
for key in preinstall install postinstall prepare; do
    body=$(jq -r --arg k "$key" '.scripts[$k] // empty' "$FILE" 2>/dev/null) || continue
    [ -n "$body" ] || continue
    if printf '%s' "$body" | grep -qiE -- "$DANGER_RE" 2>/dev/null; then
        short=$(printf '%s' "$body" | sed 's/\(.\{200\}\).*/\1.../')
        hits="${hits}  [$key] $short
"
    fi
done

if [ -n "$hits" ]; then
    printf 'Dangerous npm lifecycle install hook(s):\n'
    printf '%s' "$hits" | sed '/^[[:space:]]*$/d'
    exit 1
fi
exit 0
