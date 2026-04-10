# Shell Collector

Detects shell scripts and runs ShellCheck linting for bash/sh files.

## Overview

This collector scans repositories for shell scripts (`.sh`, `.bash` files and files with shell shebangs), identifies the shell types in use, and runs ShellCheck for automated static analysis. Results are written as both normalized lint warnings (compatible with the generic `linter` policy) and tool-specific ShellCheck data. ShellCheck is bundled in the custom collector image (`shell-main`). Shell type detection uses shebang lines; files without shebangs fall back to file extension.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.shell.script_count` | integer | Number of shell scripts detected |
| `.lang.shell.scripts` | array | File paths of detected shell scripts |
| `.lang.shell.shells` | array | Shell types found (e.g., `["bash", "sh"]`) |
| `.lang.shell.source` | object | Source metadata |
| `.lang.shell.native.shellcheck.passed` | boolean | Whether ShellCheck found no issues |
| `.lang.shell.native.shellcheck.version` | string | ShellCheck version used |
| `.lang.shell.native.shellcheck.files_checked` | integer | Number of files checked |
| `.lang.shell.native.shellcheck.error_count` | integer | Number of errors found |
| `.lang.shell.native.shellcheck.warning_count` | integer | Number of warnings found |
| `.lang.shell.native.shellcheck.info_count` | integer | Number of informational issues |
| `.lang.shell.native.shellcheck.style_count` | integer | Number of style suggestions |
| `.lang.shell.native.shellcheck.cicd.commands` | array | ShellCheck commands detected in CI |
| `.lang.shell.native.shellcheck.cicd.version` | string | ShellCheck version detected in CI |
| `.lang.shell.lint.warnings` | array | Normalized lint warnings |
| `.lang.shell.lint.linters` | array | Linters used (`["shellcheck"]`) |
| `.lang.shell.lint.source` | object | Source metadata |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects shell scripts and identifies shell types from shebangs |
| `shellcheck` | code | Runs ShellCheck and writes lint results |
| `shellcheck-cicd` | ci-before-command | Detects ShellCheck usage in CI pipelines |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/shell@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, shellcheck, shellcheck-cicd]  # Only include specific subcollectors
    # with:
    #   find_command: "find . -type f -name '*.sh' -not -path '*/node_modules/*'"  # Override file discovery
```

No configuration required. Skips gracefully if no shell scripts are found.
