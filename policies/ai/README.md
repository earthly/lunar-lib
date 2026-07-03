# AI Guardrails

Enforce AI coding assistant standards across your organization.

## Overview

This policy enforces cross-tool AI standards using data from the `ai.*` namespace. It covers code review bot presence, instruction file quality, plans directories, and AI authorship annotations.

## Policies

| Policy | Description |
|--------|-------------|
| `code-reviewer` | At least one AI code reviewer must be active (`ai.code_reviewers[]`) |
| `instruction-file-exists` | An agent instruction file must exist at the repo root |
| `canonical-naming` | Root instruction file should use the vendor-neutral name (AGENTS.md) |
| `instruction-file-length` | Root instruction file must be within configured length bounds |
| `instruction-file-sections` | Root instruction file must contain required section headings |
| `plans-dir-exists` | A dedicated AI plans directory should exist |
| `ai-authorship-annotated` | Commits should include AI authorship annotations |
| `no-undisclosed-ai` | Commits with AI fingerprints but no disclosure annotation must stay at or below the configured threshold |

## Required Data

| Path | Provided By | Description |
|------|-------------|-------------|
| `.ai.code_reviewers[]` | `coderabbit`, `claude` collectors | Normalized array of detected code review tools |
| `.ai.instructions` | `ai`, `claude`, `codex`, `gemini` collectors | Instruction file metadata — `ai` writes root/AGENTS.md, tool collectors append to `all[]` via array append |
| `.ai.plans_dir` | `ai` collector | Plans directory existence and file count |
| `.ai.authorship` | `ai` collector | AI authorship annotation coverage |
| `.ai.fingerprints` | `ai` collector | Detected AI-authorship fingerprints per commit, with a per-commit disclosed flag and an undisclosed count |

## Installation

```yaml
# Enable tool-specific collectors for code review detection:
collectors:
  - uses: github://earthly/lunar-lib/collectors/ai@main
    on: ["domain:your-domain"]
  - uses: github://earthly/lunar-lib/collectors/coderabbit@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"
  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"

# Enable the policy:
policies:
  - uses: github://earthly/lunar-lib/policies/ai@main
    enforcement: report-pr
```

## Examples

### Passing

Component has an active code reviewer and proper instruction files:

```json
{
  "ai": {
    "code_reviewers": [
      { "tool": "coderabbit", "check_name": "coderabbitai", "detected": true }
    ],
    "instructions": {
      "root": { "exists": true, "filename": "AGENTS.md", "lines": 85 }
    }
  }
}
```

### Failing

No code reviewer detected, no instruction file:

```json
{
  "ai": {
    "code_reviewers": [],
    "instructions": { "root": { "exists": false } }
  }
}
```

## Remediation

- **code-reviewer**: Enable a code review bot (CodeRabbit, Claude) and configure its collector
- **instruction-file-exists**: Create an AGENTS.md file at the repo root
- **canonical-naming**: Rename to AGENTS.md (vendor-neutral) or symlink it
- **plans-dir-exists**: Create a `.agents/plans` directory for AI agent task planning
- **ai-authorship-annotated**: Enable git-ai or add AI-model trailers to commits
- **no-undisclosed-ai**: Disclose AI-assisted commits — annotate them with git-ai notes or an `AI-` trailer (e.g. `AI-model: claude-4`) so detected fingerprints are matched by a disclosure. Tune `max_undisclosed_commits` to allow a grace threshold.
