# AI Collector

Collect tool-agnostic AI coding assistant usage data from repositories and CI pipelines.

## Overview

This collector tracks how AI coding assistants are used across your repositories and CI pipelines. It discovers agent instruction files (AGENTS.md, CLAUDE.md, etc.), checks for dedicated planning directories, detects AI CLI tools running in CI with their flags, and collects AI authorship annotations from commits.

This is the tool-agnostic portion of the `ai.*` namespace. Tool-specific collectors (`claude`, `coderabbit`) handle detection of individual tools and write to the same namespace. Refactored from `ai-use` with paths changed from `ai_use.*` to `ai.*`.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.instructions` | object | Agent instruction files: root file info, all files with sections/symlink status, per-directory grouping, total byte count |
| `.ai.plans_dir` | object | Plans directory existence, path, and file count |
| `.ai.cicd.cmds[]` | array | AI CLI tool invocations detected in CI: command string, version, and tool configuration (Codex/Gemini only; Claude moved to `claude` collector) |
| `.ai.authorship` | object | AI authorship annotation coverage across commits (Git AI notes or git trailers) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook | Description |
|-----------|------|-------------|
| `instruction-files` | `code` | Discovers AGENTS.md, CLAUDE.md, GEMINI.md, CODEX.md files with metadata and symlink status |
| `plans-dir` | `code` | Checks for a dedicated AI plans directory |
| `ai-cli-ci-codex` | `ci-after-command` (binary: codex) | Detects OpenAI Codex CLI invocations in CI |
| `ai-cli-ci-gemini` | `ci-after-command` (binary: gemini) | Detects Google Gemini CLI invocations in CI |
| `ai-authorship` | `code` | Collects AI authorship annotations from commits via Git AI standard or git trailers |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ai@main
    on: ["domain:your-domain"]
    # with:
    #   md_find_command: "find . -type f \\( -name AGENTS.md -o -name CLAUDE.md \\)"
    #   plans_dir_paths: ".agents/plans,.ai/plans"
    #   annotation_prefix: "AI-"
    #   default_branch_window: "50"
```

