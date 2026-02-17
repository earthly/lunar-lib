# AI Use Collector

Collects AI coding assistant usage data including instruction files, plans directories, CI tool invocations, and authorship annotations.

## Overview

This collector tracks how AI coding assistants are used across your repositories and CI pipelines. It discovers agent instruction files (AGENTS.md, CLAUDE.md, etc.), checks for dedicated planning directories, detects AI CLI tools running in CI with their flags, and collects AI authorship annotations from commits via the Git AI standard or git trailers.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai_use.instructions` | object | Agent instruction files: root file info, all files with sections/symlink status, per-directory grouping, total byte count |
| `.ai_use.plans_dir` | object | Plans directory existence, path, and file count |
| `.ai_use.cicd.cmds[]` | array | AI CLI tool invocations detected in CI: command string, version, and tool/MCP configuration (allowed tools, sandbox mode, approval mode) |
| `.ai_use.authorship` | object | AI authorship annotation coverage across commits (Git AI notes or git trailers) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `instruction-files` | Discovers AGENTS.md, CLAUDE.md, GEMINI.md, CODEX.md files with metadata and symlink status |
| `plans-dir` | Checks for a dedicated AI plans directory |
| `ai-cli-ci-claude` | Detects Claude Code CLI invocations in CI and flags dangerous permissions |
| `ai-cli-ci-codex` | Detects OpenAI Codex CLI invocations in CI and flags dangerous permissions |
| `ai-cli-ci-gemini` | Detects Google Gemini CLI invocations in CI and flags dangerous permissions |
| `ai-authorship` | Collects AI authorship annotations from commits via Git AI standard or git trailers |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ai-use@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
    # with:
    #   md_find_command: "find . -type f \\( -name AGENTS.md -o -name CLAUDE.md \\)"
    #   plans_dir_paths: ".agents/plans,.ai/plans"
    #   annotation_prefix: "AI-"
    #   default_branch_window: "50"
```
