# AI Use Guardrails

Enforces AI coding assistant usage standards including instruction files, naming conventions, CI safety, and authorship tracking.

## Overview

This policy plugin validates how AI coding assistants are used across your organization. It ensures repositories have properly structured instruction files, follow naming conventions, avoid dangerous CI flags, use structured output in automation, and track AI authorship in commits. These guardrails help teams adopt AI tools safely and consistently at scale.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `instruction-file-exists` | Agent instruction file must exist at repo root | No AGENTS.md, CLAUDE.md, or similar file found |
| `canonical-naming` | Root instruction file should use the canonical name | Root file is not named AGENTS.md (vendor-neutral) |
| `instruction-file-length` | Root instruction file within reasonable length bounds (set any threshold to 0 to disable) | File is too short (insufficient context) or too long (wastes token budget) |
| `instruction-file-sections` | Root instruction file contains required sections | Missing required headings like Project Overview or Build Commands |
| `symlinked-aliases` | CLAUDE.md symlinks exist alongside AGENTS.md files | Missing CLAUDE.md symlink needed for Claude Code compatibility |
| `plans-dir-exists` | Dedicated plans directory exists | No .agents/plans/ directory found |
| `ai-cli-safe-flags` | AI CLI tools in CI avoid dangerous flags | Dangerous permission-bypassing flags detected (e.g. --dangerously-skip-permissions) |
| `ai-cli-structured-output` | AI CLI tools in CI headless mode use JSON output | Headless AI CLI invocation missing structured output flag |
| `ai-authorship-annotated` | Commits include AI authorship annotations | Commits lack AI usage metadata (Git AI notes or trailers) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.ai_use.instructions` | object | [`ai-use`](https://github.com/earthly/lunar-lib/tree/main/collectors/ai-use) collector |
| `.ai_use.plans_dir` | object | [`ai-use`](https://github.com/earthly/lunar-lib/tree/main/collectors/ai-use) collector |
| `.ai_use.cicd.cmds[]` | array | [`ai-use`](https://github.com/earthly/lunar-lib/tree/main/collectors/ai-use) collector |
| `.ai_use.authorship` | object | [`ai-use`](https://github.com/earthly/lunar-lib/tree/main/collectors/ai-use) collector |

**Note:** Ensure the corresponding collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/ai-use@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [instruction-file-exists, canonical-naming]  # Only run specific checks
    # with:
    #   canonical_filename: "AGENTS.md"
    #   required_symlinks: "CLAUDE.md"
    #   min_lines: "10"            # 0 to disable
    #   max_lines: "300"           # 0 to disable
    #   max_total_bytes: "32768"   # 0 to disable
    #   required_sections: "Project Overview,Build Commands"
```

## Examples

### Passing Example

A repository with a properly configured AGENTS.md, CLAUDE.md symlink, and plans directory:

```json
{
  "ai_use": {
    "instructions": {
      "root": {
        "exists": true,
        "filename": "AGENTS.md",
        "lines": 85,
        "sections": ["Project Overview", "Architecture", "Build Commands"]
      },
      "count": 3,
      "total_bytes": 4200,
      "directories": [
        {
          "dir": ".",
          "files": [
            { "filename": "AGENTS.md", "is_symlink": false },
            { "filename": "CLAUDE.md", "is_symlink": true, "symlink_target": "AGENTS.md" }
          ]
        }
      ]
    },
    "plans_dir": { "exists": true, "path": ".agents/plans", "file_count": 2 },
    "cicd": {
      "cmds": [
        { "cmd": "claude -p --output-format json 'review this'", "tool": "claude", "version": "1.0.20" }
      ]
    },
    "authorship": { "total_commits": 10, "annotated_commits": 8 }
  }
}
```

### Failing Examples

#### No instruction file at root (fails `instruction-file-exists`)

```json
{
  "ai_use": {
    "instructions": {
      "root": { "exists": false },
      "count": 0,
      "total_bytes": 0
    }
  }
}
```

**Failure message:** `"No agent instruction file found at repository root (expected AGENTS.md, CLAUDE.md, GEMINI.md, or CODEX.md)"`

#### Only CLAUDE.md at root, no AGENTS.md (fails `canonical-naming`)

```json
{
  "ai_use": {
    "instructions": {
      "root": { "exists": true, "filename": "CLAUDE.md", "lines": 50 }
    }
  }
}
```

**Failure message:** `"Root instruction file is CLAUDE.md — rename to AGENTS.md and create CLAUDE.md as a symlink (Claude Code requires the symlink)"`

#### Dangerous CI flags detected (fails `ai-cli-safe-flags`)

```json
{
  "ai_use": {
    "cicd": {
      "cmds": [
        {
          "cmd": "claude --dangerously-skip-permissions -p 'deploy to prod'",
          "tool": "claude",
          "version": "1.0.20"
        }
      ]
    }
  }
}
```

**Failure message:** `"claude CI invocation uses dangerous flag: --dangerously-skip-permissions"`

## Remediation

### instruction-file-exists

Create an AGENTS.md file at the repository root with project context for AI coding assistants. Include sections covering project overview, build commands, and testing instructions.

### canonical-naming

Rename your instruction file to AGENTS.md (the vendor-neutral canonical name) and create symlinks for tool-specific names:

```bash
mv CLAUDE.md AGENTS.md
ln -s AGENTS.md CLAUDE.md
```

### instruction-file-length

If too short: add meaningful content — project overview, architecture notes, build commands, testing patterns, and common gotchas. If too long: use progressive disclosure — keep the root file focused and create subdirectory AGENTS.md files for module-specific details. Codex hard-caps at 32KB combined. Set any threshold to `"0"` to disable that specific check.

### instruction-file-sections

Add the missing required sections as markdown headings. Default required sections are `## Project Overview` and `## Build Commands`. Customize via the `required_sections` input.

### symlinked-aliases

Create CLAUDE.md as a symlink to AGENTS.md in each directory that has an instruction file:

```bash
ln -s AGENTS.md CLAUDE.md
```

### plans-dir-exists

Create a dedicated plans directory for AI agent task planning:

```bash
mkdir -p .agents/plans
```

### ai-cli-safe-flags

Remove dangerous permission-bypassing flags from AI CLI invocations in CI. Use scoped permissions instead: Claude's `allowedTools`, Codex's `execpolicy` rules, or Gemini's sandbox profiles.

### ai-cli-structured-output

Add structured output flags to headless AI CLI invocations in CI: `--output-format json` for Claude/Gemini, `--json` for Codex.

### ai-authorship-annotated

Install [Git AI](https://usegitai.com) for automated line-level AI authorship tracking, or add git trailers manually to commits: `AI-model: claude-4`, `AI-tool: cursor`.
