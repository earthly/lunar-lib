# AI Native Starter Pack

For teams using AI coding agents (Claude Code, Codex, Gemini CLI) in development and CI. Ensures AI instruction files exist and follow conventions, dangerous CLI flags are caught, and AI-generated code goes through proper quality gates.

## What's Included

### Collectors
| Collector | Purpose |
|-----------|---------|
| All language collectors | Only trigger when the language is detected |
| `ai-use` | AI instruction files, CLI usage in CI, authorship annotations |
| `gitleaks` | Secret scanning |
| `github-actions` | GitHub Actions workflow analysis |
| `github` | Repo settings |

### Policies

**AI Guardrails (all at score)**
| Policy | Check | What it does |
|--------|-------|-------------|
| `ai-use` | `instruction-file-exists` | Repo has an AGENTS.md, CLAUDE.md, or similar |
| `ai-use` | `canonical-naming` | Root instruction file is named AGENTS.md |
| `ai-use` | `instruction-file-length` | Instruction file is between 10–300 lines |
| `ai-use` | `ai-cli-safe-flags` | No dangerous flags (--dangerously-skip-permissions, --yolo, --full-auto) in CI |
| `ai-use` | `ai-cli-structured-output` | AI CLI in headless CI uses JSON output |
| `ai-use` | `ai-authorship-annotated` | Tracks AI authorship annotations (passive by default) |

**Supporting Checks**
| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `secrets` | `no-hardcoded-secrets` | **report-pr** | AI tools can accidentally include secrets |
| `github-actions` | `no-script-injection`, `permissions-declared` | score | CI security when AI CLIs run in workflows |
| `vcs` | `branch-protection-enabled`, `require-pull-request` | score | Governance when AI agents push code |
| `testing` | `executed`, `passing` | score | AI-generated code needs test coverage |
| `linter` | `ran` | score | AI-generated code needs lint checks |

## Enforcement Philosophy

- **report-pr**: Secret detection only — AI tools are more likely to accidentally include secrets than human developers
- **score**: Everything else — gives your team an AI development health dashboard without PR friction on day 1

## Tightening Over Time

As your AI development practices mature, consider promoting:
1. `ai-use.instruction-file-exists` → `report-pr` (once all repos have instruction files)
2. `ai-use.ai-cli-safe-flags` → `report-pr` (once CI pipelines are standardized)
3. Add `ai-use.instruction-file-sections` to enforce required sections in instruction files
4. Add `ai-use.symlinked-aliases` to ensure CLAUDE.md symlinks alongside AGENTS.md
5. Raise `ai-use.ai-authorship-annotated` threshold with `min_annotation_percentage` to enforce annotation coverage
