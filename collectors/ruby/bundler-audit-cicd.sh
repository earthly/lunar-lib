#!/bin/bash
set -e

# CI collector — fires after `bundle audit` completes in CI
# Runs native on CI runner — avoid jq

BUNDLE_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-bundle}"

# Re-run audit to get parseable output
set +e
audit_output=$("$BUNDLE_BIN" audit check 2>&1)
audit_exit=$?
set -e

if [[ $audit_exit -eq 0 ]]; then
    # Clean — no vulnerabilities
    lunar collect -j ".lang.ruby.bundler_audit" \
        '{"vulnerabilities":[],"source":{"tool":"bundler-audit","integration":"ci"}}'
else
    # Parse vulnerability blocks and build JSON manually (no jq available)
    vulns=""
    first=true
    gem_name="" gem_ver="" advisory="" title="" crit=""

    while IFS= read -r line; do
        case "$line" in
            Name:*)        gem_name=$(echo "$line" | sed 's/^Name:[[:space:]]*//') ;;
            Version:*)     gem_ver=$(echo "$line" | sed 's/^Version:[[:space:]]*//') ;;
            Advisory:*|CVE:*|GHSA:*)
                           advisory=$(echo "$line" | sed 's/^[A-Za-z]*:[[:space:]]*//') ;;
            Criticality:*) crit=$(echo "$line" | sed 's/^Criticality:[[:space:]]*//') ;;
            Title:*)       title=$(echo "$line" | sed 's/^Title:[[:space:]]*//') ;;
            "")
                if [[ -n "$gem_name" ]]; then
                    title_esc=$(printf '%s' "$title" | sed 's/\\/\\\\/g; s/"/\\"/g')
                    [[ "$first" != "true" ]] && vulns="$vulns,"
                    vulns="$vulns{\"gem\":\"$gem_name\",\"version\":\"$gem_ver\",\"advisory\":\"$advisory\",\"title\":\"$title_esc\",\"criticality\":\"$crit\"}"
                    first=false
                    gem_name="" gem_ver="" advisory="" title="" crit=""
                fi
                ;;
        esac
    done <<< "$audit_output"

    # Catch last block
    if [[ -n "$gem_name" ]]; then
        title_esc=$(printf '%s' "$title" | sed 's/\\/\\\\/g; s/"/\\"/g')
        [[ "$first" != "true" ]] && vulns="$vulns,"
        vulns="$vulns{\"gem\":\"$gem_name\",\"version\":\"$gem_ver\",\"advisory\":\"$advisory\",\"title\":\"$title_esc\",\"criticality\":\"$crit\"}"
    fi

    lunar collect -j ".lang.ruby.bundler_audit" \
        "{\"vulnerabilities\":[$vulns],\"source\":{\"tool\":\"bundler-audit\",\"integration\":\"ci\"}}"
fi
