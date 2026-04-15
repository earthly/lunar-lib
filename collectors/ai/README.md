# AI Collector

Collect tool-agnostic AI coding assistant usage data from repositories.

## Overview

This collector tracks tool-agnostic AI coding assistant usage across your repositories. It discovers the vendor-neutral AGENTS.md instruction file, checks for dedicated planning directories, and collects AI authorship annotations from commits. Tool-specific instruction files (CLAUDE.md, CODEX.md, GEMINI.md) are discovered by their respective tool collectors.

This is the tool-agnostic portion of the `ai.*` namespace. Tool-specific collectors (`claude`, `coderabbit`, `codex`, `gemini`) handle detection of individual tools.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.instructions` | object | Agent instruction files: root file info, all files with sections/symlink status, per-directory grouping, total byte count |
| `.ai.plans_dir` | object | Plans directory existence, path, and file count |
| `.ai.authorship` | object | AI authorship annotation coverage across commits (Git AI notes or git trailers) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook | Description |
|-----------|------|-------------|
| `instruction-files` | `code` | Discovers AGENTS.md files with metadata and symlink status |
| `plans-dir` | `code` | Checks for a dedicated AI plans directory |
| `ai-authorship` | `code` | Collects AI authorship annotations from commits via Git AI standard or git trailers |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ai@main
    on: ["domain:your-domain"]
    # with:
    #   md_find_command: "find . -type f -name AGENTS.md"
    #   plans_dir_paths: ".agents/plans,.ai/plans"
    #   annotation_prefix: "AI-"
    #   default_branch_window: "50"
```

