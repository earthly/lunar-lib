# AI Use Guardrails — Collector + Policy Plan

Collectors and policies under an `ai-use` plugin to enforce AI usage standards at scale.

---

## Component JSON: `.ai_use` category

New top-level category — follows convention #1 ("categories describe WHAT, not HOW"). AI-assisted development is its own concern, like `.testing` or `.sca`.

**Key paths:**

| Path | Description |
|------|-------------|
| `.ai_use.instructions.root` | Root-level instruction file info (`exists`, `filename`, `lines`, `bytes`, `sections[]`) |
| `.ai_use.instructions.all[]` | Every instruction file in the repo (see per-file schema below) |
| `.ai_use.instructions.count` | Total count of instruction files found |
| `.ai_use.instructions.total_bytes` | Combined size in bytes of all instruction files (for context window budget) |
| `.ai_use.instructions.directories[]` | Per-directory view: `dir`, `files[]` (filenames + symlink info for that directory) |
| `.ai_use.instructions.source` | Source metadata (`tool: "find"`, `integration: "code"`) |
| `.ai_use.plans_dir` | Plans directory info (`exists`, `path`, `file_count`) |
| `.ai_use.cicd.cmds[]` | AI CLI invocations detected in CI (see per-tool schema below) |
| `.ai_use.authorship.provider` | How authorship data was collected: `"git-ai"` or `"trailers"` |
| `.ai_use.authorship.total_commits` | Total commits in scope |
| `.ai_use.authorship.annotated_commits` | Count with any AI annotation |
| `.ai_use.authorship.git_ai` | Git AI specific: `notes_ref_exists`, `commits_with_notes` (if git-ai is installed) |
| `.ai_use.authorship.trailers` | Trailer-based: per-commit details (`sha`, `model`, `tokens`, `has_annotation`) |

**Per-file schema for `.ai_use.instructions.all[]`:**

```json
{
  "path": "src/backend/AGENTS.md",
  "dir": "src/backend",
  "filename": "AGENTS.md",
  "lines": 45,
  "bytes": 2048,
  "sections": ["Project Overview", "Build Commands", "Testing"],
  "is_symlink": false,
  "symlink_target": null
}
```

The collector discovers all known instruction file names: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CODEX.md` (configurable). It records each file neutrally — filename, whether it's a symlink, and what it points to. Policies then decide which filenames are canonical and which should be symlinks.

**Per-directory schema for `.ai_use.instructions.directories[]`:**

```json
{
  "dir": "src/backend",
  "files": [
    { "filename": "AGENTS.md", "is_symlink": false },
    { "filename": "CLAUDE.md", "is_symlink": true, "symlink_target": "AGENTS.md" }
  ]
}
```

This makes it easy for policies to check per-directory invariants (e.g., "every directory with an instruction file should also have a CLAUDE.md symlink").

**Design notes:**

- `instructions.root.exists` is an explicit boolean — the collector always runs and writes `true` or `false` (Pattern 2 from conventions: always-checked property). True if *any* instruction file exists at root.
- `instructions.root.filename` records which file is at root (e.g., `AGENTS.md` or `CLAUDE.md`) — policy decides if the name is acceptable
- `.ai_use.cicd` follows the `.cicd` sub-key convention (tool detected running in CI)
- `.ai_use.authorship` is the normalized path; `git_ai` and `trailers` are two possible data sources (tool-agnostic normalization — convention #2)
- The collector is opinion-free about file naming — it collects data for all recognized filenames; naming policy is enforced by the policy plugin only

---

## Collector plugin: `collectors/ai-use`

**Categories:** `code-analysis`, `ci-cd` (technology-aligned, per collector convention)

### Subcollectors

#### 1. `instruction-files` (hook: `code`)

- Find all recognized agent instruction files in repo (recursive): `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CODEX.md`
- Input: `md_find_command` — exposes the `find` command used under the hood (Pattern A from collector reference), default: `find . -type f \( -name AGENTS.md -o -name CLAUDE.md -o -name GEMINI.md -o -name CODEX.md \) -not -path '*/node_modules/*' -not -path '*/.git/*'`
- For each file found: record path, directory, filename, line count, byte size, parsed markdown headings (sections), whether it's a symlink and what it targets
- For root directory: record whether any instruction file exists (`true`/`false`), which filename, its metrics
- Group files by directory for the `directories[]` view (makes per-directory policy checks easy)
- Compute `total_bytes` across all non-symlink files (relevant for context window budgets — Codex hard caps at 32KB by default). Symlinks don't count toward budget since they point to already-counted files.
- Write to `.ai_use.instructions`
- Strategy 8 (File Parsing)
- **The collector is opinion-free about naming** — it discovers and records everything; naming policy comes from the policy plugin

#### 2. `plans-dir` (hook: `code`)

- Check if configured plans directory exists
- Tries candidate paths in order (first match wins) — Pattern B from collector reference
- Count files in it
- Write to `.ai_use.plans_dir`
- Input: `plans_dir_paths` (comma-separated candidate paths, default `.agents/plans,.ai/plans`)

#### 3. `ai-cli-ci-claude` (hook: `ci-after-command`)

Detect Claude Code CLI invocations in CI.

- Hook match: binary name `claude`
- Record: command string, version (`claude --version`)
- Flag dangerous flags:
  - `--dangerously-skip-permissions` — bypasses all permission prompts
  - `--allow-dangerously-skip-permissions` — enables the bypass option
- Flag missing structured output (when in `-p` / `--print` mode):
  - Expect one of: `--output-format json`, `--output-format stream-json`, `--json-schema`
- Collect into `.ai_use.cicd.cmds[]` (auto-concatenation)
- Runs `native` (CI collector)

#### 4. `ai-cli-ci-codex` (hook: `ci-after-command`)

Detect OpenAI Codex CLI invocations in CI.

- Hook match: binary name `codex`
- Record: command string, version
- Flag dangerous flags:
  - `--dangerously-bypass-approvals-and-sandbox` (also `--yolo`) — bypasses all approvals and sandboxing
  - `--sandbox danger-full-access` — disables sandbox entirely
  - `--full-auto` — low-friction mode, skips most approvals
  - `--ask-for-approval never` — never asks for approval
- Flag missing structured output (when in `exec` mode):
  - Expect: `--json` / `--experimental-json`, or `--output-schema`
- Collect into `.ai_use.cicd.cmds[]` (auto-concatenation)
- Runs `native` (CI collector)

#### 5. `ai-cli-ci-gemini` (hook: `ci-after-command`)

Detect Google Gemini CLI invocations in CI.

- Hook match: binary name `gemini`
- Record: command string, version
- Flag dangerous flags:
  - `--yolo` / `-y` — auto-approves all actions without prompting
  - `--approval-mode auto_edit` — auto-approves edits
- Flag missing structured output (when in `-p` / `--prompt` mode):
  - Expect: `--output-format json`
- Collect into `.ai_use.cicd.cmds[]` (auto-concatenation)
- Runs `native` (CI collector)

**Shared CI collector schema for `.ai_use.cicd.cmds[]`:**

```json
{
  "cmd": "claude -p --output-format json --allowedTools Bash(git*) Read 'review this'",
  "tool": "claude",
  "version": "1.2.0",
  "allowed_tools": "Bash(git*) Read"
}
```

Collectors record what happened — `cmd`, `tool`, `version`, plus tool/MCP configuration extracted from CLI flags:

| Field | Tools | Source flag |
|-------|-------|------------|
| `allowed_tools` | Claude | `--allowedTools` |
| `disallowed_tools` | Claude | `--disallowedTools` |
| `tools_restriction` | Claude | `--tools` |
| `mcp_config` | Claude | `--mcp-config` |
| `sandbox` | Codex, Gemini | `--sandbox` / `-s` |
| `approval_mode` | Codex, Gemini | `--ask-for-approval` / `--approval-mode` |

Fields are only present when the flag was used. All judgment (dangerous flags, headless detection, structured output) is done by the policy.

#### 6. `ai-authorship` (hook: `code`)

Collect AI authorship data from commits. Supports two mechanisms:

**a) Git AI standard (preferred, if installed)**
- Check if `refs/notes/ai` exists (the Git AI notes ref)
- For PR context: scan PR commits for git-ai notes
- For default branch: scan recent commits (configurable window)
- Extract from notes: tool, model, accepted_lines, overridden_lines per prompt
- Reference: [Git AI Standard v3.0.0](https://github.com/git-ai-project/git-ai/blob/main/specs/git_ai_standard_v3.0.0.md)
- Reference: [usegitai.com](https://usegitai.com)

**b) Git trailers fallback**
- Parse commit messages for trailers with configurable prefix (default `AI-`)
- Look for: `AI-model:`, `AI-tokens:`, `AI-tool:`, `AI-assisted: true`
- Write summary stats + per-commit details to `.ai_use.authorship`

Inputs:
- `annotation_prefix` (default `AI-`)
- `default_branch_window` (default `50`)

---

## Policy plugin: `policies/ai-use`

**Category:** `devex-build-and-ci`
**Requires:** `ai-use` collector

### Checks

#### 1. `instruction-file-exists`

- An agent instruction file must exist at the repo root
- `assert_true(get_value(".ai_use.instructions.root.exists"), ...)`
- Passes if *any* recognized instruction file exists at root (AGENTS.md, CLAUDE.md, etc.)
- Simple boolean — collector always writes true/false

#### 2. `canonical-naming`

- The root instruction file should be named AGENTS.md (vendor-neutral canonical name)
- Reads `.ai_use.instructions.root.filename` — fails if root file exists but is not `AGENTS.md`
- A repo with only `CLAUDE.md` at root: passes `instruction-file-exists` (file exists), fails `canonical-naming` (wrong name)
- Input: `canonical_filename` (default `AGENTS.md`) — allows orgs to pick a different canonical name if desired
- Failure message adapts to the filename found:
  - `CLAUDE.md` → "Rename to `AGENTS.md` and create `CLAUDE.md` as a symlink" (Claude Code doesn't support AGENTS.md, so the symlink is needed)
  - `GEMINI.md`, `CODEX.md`, etc. → "Rename to `AGENTS.md`" (these tools support AGENTS.md natively, no symlink needed)

#### 3. `instruction-file-length`

- Root instruction file should be within reasonable bounds (regardless of its filename)
- Configurable `min_lines` (default `10`) and `max_lines` (default `300`)
- Based on research:
  - Codex hard-caps at 32KB combined across all instruction files
  - Studies show excessive context reduces task success rates and increases cost 20%+ ([arxiv.org/html/2602.11988v1](https://arxiv.org/html/2602.11988v1))
  - Recommended pattern: 3-layer progressive disclosure (global < 20 lines, project < 50 lines per layer, module-specific focused)
- Failure when too long: recommend progressive disclosure — split into subdirectory files, link to external docs
- Failure when too short: suggest adding project overview, build commands, architecture notes
- Also check `total_bytes` against a configurable `max_total_bytes` (default `32768` — matching Codex default)

#### 4. `instruction-file-sections`

- Root instruction file must contain required sections (parsed from heading text)
- Applies to whatever instruction file is at root — checks content, not filename
- Input: `required_sections` (comma-separated heading substrings, default `Project Overview,Build Commands`)
- Match is case-insensitive substring against parsed section headings
- Sensible default covers the basics; orgs can customize

#### 5. `symlinked-aliases`

- Every directory with an AGENTS.md should also have a CLAUDE.md symlink pointing to it
- Only CLAUDE.md requires a symlink — Claude Code doesn't support the AGENTS.md filename natively. Other tools (Gemini, Codex) support AGENTS.md directly, so no symlinks needed for them.
- Iterates `.ai_use.instructions.directories[]` — for each directory with the canonical file, checks that a CLAUDE.md symlink exists
- Input: `canonical_filename` (default `AGENTS.md`), `required_symlinks` (comma-separated, default `CLAUDE.md`)
- A directory with `AGENTS.md` but no `CLAUDE.md` symlink: fails — suggests `ln -s AGENTS.md CLAUDE.md`
- A directory with only `CLAUDE.md` (not a symlink): fails — suggests creating `AGENTS.md` as the real file and symlinking `CLAUDE.md` to it
- Failure message includes which directories and which symlinks are missing

#### 6. `plans-dir-exists`

- Dedicated plans directory should exist
- `assert_true(get_value(".ai_use.plans_dir.exists"), ...)`
- Failure message references the expected path

#### 7. `ai-cli-safe-flags`

- AI CLI tools used in CI should not use dangerous flags
- Iterate `.ai_use.cicd.cmds[]`, parse `cmd` string to check for dangerous flags
- Dangerous flags are configurable per-tool via policy inputs:
  - `dangerous_flags_claude` (default: `--dangerously-skip-permissions,--allow-dangerously-skip-permissions`)
  - `dangerous_flags_codex` (default: `--dangerously-bypass-approvals-and-sandbox,--yolo,--full-auto`)
  - `dangerous_flags_gemini` (default: `--yolo,-y`)
- Failure message includes the specific tool, command, and which flag violated
- If no CI AI CLI usage detected → skip (not applicable)

#### 8. `ai-cli-structured-output`

- AI CLI tools in CI headless/automation mode should use structured (JSON) output
- Iterate `.ai_use.cicd.cmds[]` where `is_headless` is true
- Assert `has_structured_output` is true for each
- Rationale: JSON output makes AI automation deterministic and parseable; raw text output in CI is fragile
- If no headless CI AI CLI usage detected → skip (not applicable)

#### 9. `ai-authorship-annotated`

- Commits should be annotated with AI usage metadata
- Configurable `min_annotation_percentage` (default `0` — awareness mode)
- When threshold is 0: pass as long as data exists (visible in dashboards for tracking)
- Suggested rollout: start at `report-pr` to build awareness before enforcing
- Failure message references [usegitai.com](https://usegitai.com) as the recommended tool for automated line-level tracking, or git trailers as a lightweight manual alternative

---

## Implementation phases

### Phase 1: YAMLs and READMEs only — pause for human review ✅

Create the plugin scaffolding, manifests, and documentation. No scripts yet.

**Collector (`collectors/ai-use/`):**
- `lunar-collector.yml` — full manifest with all 6 subcollectors defined, inputs, landing page metadata, example component JSON
- `README.md` — matching the collector README template
- `assets/ai-use.svg` — 2x2 grid icon with Claude, OpenAI, Gemini logos (from Wikimedia Commons) + generic robot

**Policy (`policies/ai-use/`):**
- `lunar-policy.yml` — full manifest with all 9 checks defined, inputs, landing page metadata, requires section
- `README.md` — matching the policy README template (with Passing/Failing examples, Remediation per check)
- `assets/ai-use.svg` — standalone robot head icon (distinct from collector icon)
- `requirements.txt` — `lunar-policy==0.2.2`

**Validation:** All three validation scripts pass clean (landing page metadata, README structure, SVG grayscale).

**Status:** Complete. Human review in progress.

### Phase 2: Implement collectors ✅

**Scripts implemented:**

| Script | Hook | Runtime | Description |
|--------|------|---------|-------------|
| `instruction-files.sh` | `code` | containerized (jq) | Finds all AGENTS.md/CLAUDE.md/etc., parses headings, detects symlinks, groups by directory |
| `plans-dir.sh` | `code` | containerized (jq) | Tries candidate paths in order, counts files |
| `helpers.sh` | — | native (pure bash) | Shared: `get_tool_version`, `parse_cmd_str`, `extract_flag_value`, `extract_flag_values` |
| `ai-cli-ci.sh` | `ci-after-command` | native | Single script for all three tools — tool name derived from `LUNAR_CI_COMMAND[0]` |
| `ai-authorship.sh` | `code` | containerized (jq) | Checks `refs/notes/ai` first (Git AI), falls back to trailer parsing |

**Key design decisions made during Phase 2:**
- **CI collectors consolidated** — all three (claude, codex, gemini) share one `ai-cli-ci.sh` script; tool name extracted from the command itself, not a config var
- **Collectors are opinion-free** — record raw facts (`cmd`, `tool`, `version`, config flags); no dangerous flag judgment, no headless detection. All analysis in the policy.
- **Tool/MCP config extracted** as structured fields per tool (present only when the flag was used):
  - Claude: `allowed_tools`, `disallowed_tools`, `tools_restriction`, `mcp_config`
  - Codex: `sandbox`, `approval_mode`
  - Gemini: `sandbox`, `approval_mode`
  - No built-in policies for these yet — data is available for custom user policies
- **Dangerous flags are policy inputs** (`dangerous_flags_claude`, `dangerous_flags_codex`, `dangerous_flags_gemini`) with researched defaults, not collector concerns

### Phase 3: Implement policies ✅

All 9 policy checks implemented, flat in the plugin root. Each follows `def main(node=None)` pattern for testability.

| Policy | Missing data handling | Key behavior |
|--------|-----------------------|-------------|
| `instruction_file_exists.py` | `get_value` → PENDING | Assert boolean from collector |
| `canonical_naming.py` | `get_value` → PENDING | Pass silently if no root file; tool-specific rename advice |
| `instruction_file_length.py` | `get_value` + defaults to 0 | Three thresholds (min_lines, max_lines, max_total_bytes), each disableable with 0 |
| `instruction_file_sections.py` | `get_value` → PENDING | Fail if no root file; error if required_sections misconfigured |
| `symlinked_aliases.py` | `get_value` → PENDING | Per-directory: canonical must be real file, required symlinks must exist |
| `plans_dir_exists.py` | `get_value` → PENDING | Simple boolean |
| `ai_cli_safe_flags.py` | skip if no CI data | Parses cmd string against per-tool configurable dangerous flag lists |
| `ai_cli_structured_output.py` | skip if no CI data | Detects headless mode per-tool, checks for JSON output flags |
| `ai_authorship_annotated.py` | `get_value` → PENDING | Default 0% = always passes; nonzero enforces annotation coverage |

**Key design decisions made during Phase 3:**
- **`def main(node=None)` pattern** on all policies for testability (Pattern 3 from reference)
- **`get_value` for required collector data** — goes PENDING until collector finishes, never masks missing data with defaults
- **`get_value_or_default` only for optional fields** within already-collected data (e.g. sections array, lines when file doesn't exist)
- **Length thresholds disableable with 0** — set any of `min_lines`, `max_lines`, `max_total_bytes` to `"0"` to skip that check
- **`instruction_file_sections` raises ValueError on misconfiguration** — empty `required_sections` is an error, not a silent pass
- **`instruction_file_sections` fails (not passes) when no root file** — missing sections is a real failure regardless of file existence
- **No unnecessary comments** — code is self-evident
- **CI policies use `c.skip()`** — only for applicability (no AI CLI detected), not for missing data

### Phase 4: Update Component JSON documentation ✅

- Created `ai-context/component-json/cat-ai-use.md` — full category doc with example JSON (instructions, plans_dir, cicd, authorship) and 15 key policy paths
- Updated `ai-context/component-json/structure.md` — added `.ai_use` to both the quick reference table (11 rows) and the category documentation list

---

## Resolved decisions

- **Collector is naming-neutral** — discovers all recognized instruction filenames (AGENTS.md, CLAUDE.md, GEMINI.md, CODEX.md); records each file's name, metrics, and symlink status without opinions
- **Policy enforces naming** — `canonical-naming` check asserts the root file should be AGENTS.md (configurable); `symlinked-aliases` check asserts companion symlinks exist
- **A repo with only CLAUDE.md** passes `instruction-file-exists` and content checks (length, sections) but fails `canonical-naming` — useful for gradual adoption
- **Plans directory**: just existence + file count, no format validation
- **Dangerous flags are per-tool policy inputs** — not collector concerns; defaults researched from official CLI docs
- **Tool/MCP config collected but no built-in policies** — `allowed_tools`, `sandbox`, `approval_mode` etc. extracted for custom user policies
- **JSON output enforcement**: worth doing — new check `ai-cli-structured-output`
- **Commit annotations**: support both Git AI standard (line-level, automated) and git trailers (lightweight, manual) — collector auto-detects which is available
- **Input patterns**: `md_find_command` for instruction file discovery (Pattern A — find command); `plans_dir_paths` for plans directory (Pattern B — ordered candidate paths, first match wins)
- **Collector categories** use technology-aligned values (`code-analysis`, `ci-cd`); policy category uses verification-aligned (`devex-build-and-ci`) — per validation script conventions
- **Icons**: collector uses 2x2 grid of real logos (Claude, OpenAI, Gemini from Wikimedia Commons + generic robot); policy uses standalone robot head — visually distinct
- **CI hooks** use structured `binary.name` matching (not regex `pattern`) per collector reference best practices
- **Policy files flat in plugin root** (no `checks/` subdirectory) — matching existing plugins like `policies/testing/`
- **Length thresholds individually disableable** — set `min_lines`, `max_lines`, or `max_total_bytes` to `"0"` to skip; when no file exists, lines/bytes default to 0 so min_lines naturally fails
- **Sections check fails when no root file** — missing sections is a failure, not a silent pass (unlike canonical-naming which defers to the existence check)
- **Empty required_sections is a misconfiguration error** — not a silent pass (allow-list pattern from reference)

## Other changes made during Phase 1

- Updated `ai-context/policy-reference.md` to remove `checks/` subdirectory pattern (flat file layout)
- Updated `skills/lunar-policy/SKILL.md` to match (committed and pushed to `skills` main)
- Updated `ai-context/collector-reference.md` to merge Pattern B and C into a single "Single Item with Multiple Candidate Paths" pattern covering both files and directories
