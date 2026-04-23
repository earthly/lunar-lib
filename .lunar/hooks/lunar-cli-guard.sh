#!/bin/bash
# lunar-cli-guard.sh — PreToolUse hook for Bash.
# Validates execution context before lunar CLI commands run.
# Exit 0 = allow, Exit 2 = block (stderr shown to Claude)

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r ".tool_input.command // empty")
CWD=$(echo "$INPUT" | jq -r ".cwd // empty")

# Extract actual lunar CLI invocations (not "lunar" appearing in paths,
# filenames, string literals, etc). Match `lunar` only at the start of a
# command word: beginning of line, after `&&`, `||`, `|`, `;`, or newline.
# Then capture the rest of that command segment (up to the next separator).
LUNAR_INVOCATIONS=$(echo "$COMMAND" | grep -oE '(^|[\&\|\;[:space:]])lunar([[:space:]][^|&;]*)?' | sed -E 's/^[[:space:]&|;]*//')
[ -z "$LUNAR_INVOCATIONS" ] && exit 0

# If every lunar invocation is --help / --version / `lunar` alone, skip checks.
NON_HELP=$(echo "$LUNAR_INVOCATIONS" | grep -vE '^lunar([[:space:]]|$).*(--help|--version|-h\b|-v\b)' | grep -vE '^lunar[[:space:]]*$')
[ -z "$NON_HELP" ] && exit 0

if [ -z "$LUNAR_HUB_TOKEN" ]; then
  echo "LUNAR_HUB_TOKEN is not set. Export it before running lunar commands:" >&2
  echo "  export LUNAR_HUB_TOKEN=<token>" >&2
  echo "Token comes from the hub deployment (see your agent environment secrets)." >&2
  exit 2
fi

# Determine the effective working directory for the lunar command.
# If the command starts with `cd <path> && ...`, honour that cd target.
# Otherwise fall back to Claude's reported CWD.
# Supports: `cd /abs/path`, `cd ~/rel`, `cd "path with spaces"`, `cd 'path'`.
EFFECTIVE_CWD="$CWD"
TRIMMED="${COMMAND#"${COMMAND%%[![:space:]]*}"}"
if [[ "$TRIMMED" =~ ^cd[[:space:]]+ ]]; then
  REST="${TRIMMED#cd}"
  REST="${REST#"${REST%%[![:space:]]*}"}"
  if [[ "$REST" =~ ^\"([^\"]+)\"[[:space:]]*\&\&(.*)$ ]]; then
    CD_PATH="${BASH_REMATCH[1]}"
  elif [[ "$REST" =~ ^\'([^\']+)\'[[:space:]]*\&\&(.*)$ ]]; then
    CD_PATH="${BASH_REMATCH[1]}"
  elif [[ "$REST" =~ ^([^[:space:]\&\|\;]+)[[:space:]]*\&\&(.*)$ ]]; then
    CD_PATH="${BASH_REMATCH[1]}"
  else
    CD_PATH=""
  fi
  if [ -n "$CD_PATH" ]; then
    CD_PATH="${CD_PATH/#\~/$HOME}"
    EFFECTIVE_CWD="$CD_PATH"
  fi
fi

# For lunar commands that talk to the hub / read plugin manifests
# (collector, policy, component, catalog, sql, secret, hub), require a
# lunar-config.yml in the effective working directory.
if echo "$NON_HELP" | grep -qE '^lunar (collector|policy|component|catalog|sql|secret|hub)\b'; then
  if [ ! -f "$EFFECTIVE_CWD/lunar-config.yml" ] && [ ! -f "$EFFECTIVE_CWD/lunar-config.yaml" ]; then
    echo "No lunar-config.yml in effective directory ($EFFECTIVE_CWD)." >&2
    echo "Run lunar commands from a directory with lunar-config.yml, e.g.:" >&2
    echo "  cd ~/repos/pantalasa-cronos-lunar && lunar collector dev ..." >&2
    echo "  cd ~/repos/pantalasa-cronos/lunar && lunar collector dev ..." >&2
    exit 2
  fi
fi

exit 0
