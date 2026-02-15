# Category: `.ai_use`

AI coding assistant usage — instruction files, plans directories, CI tool invocations, and authorship annotations.

```json
{
  "ai_use": {
    "instructions": {
      "root": {
        "exists": true,
        "filename": "AGENTS.md",
        "lines": 85,
        "bytes": 3200,
        "sections": ["Project Overview", "Architecture", "Build Commands", "Testing"]
      },
      "all": [
        {
          "path": "AGENTS.md",
          "dir": ".",
          "filename": "AGENTS.md",
          "lines": 85,
          "bytes": 3200,
          "sections": ["Project Overview", "Architecture", "Build Commands", "Testing"],
          "is_symlink": false,
          "symlink_target": null
        },
        {
          "path": "CLAUDE.md",
          "dir": ".",
          "filename": "CLAUDE.md",
          "lines": 85,
          "bytes": 3200,
          "sections": ["Project Overview", "Architecture", "Build Commands", "Testing"],
          "is_symlink": true,
          "symlink_target": "AGENTS.md"
        },
        {
          "path": "src/backend/AGENTS.md",
          "dir": "src/backend",
          "filename": "AGENTS.md",
          "lines": 40,
          "bytes": 1500,
          "sections": ["Overview", "API Endpoints"],
          "is_symlink": false,
          "symlink_target": null
        }
      ],
      "count": 3,
      "total_bytes": 4700,
      "directories": [
        {
          "dir": ".",
          "files": [
            { "filename": "AGENTS.md", "is_symlink": false },
            { "filename": "CLAUDE.md", "is_symlink": true, "symlink_target": "AGENTS.md" }
          ]
        },
        {
          "dir": "src/backend",
          "files": [
            { "filename": "AGENTS.md", "is_symlink": false }
          ]
        }
      ],
      "source": { "tool": "find", "integration": "code" }
    },
    "plans_dir": {
      "exists": true,
      "path": ".agents/plans",
      "file_count": 3
    },
    "cicd": {
      "cmds": [
        {
          "cmd": "claude -p --output-format json --allowedTools Bash(git*) Read 'review this PR'",
          "tool": "claude",
          "version": "1.0.20",
          "allowed_tools": "Bash(git*) Read"
        },
        {
          "cmd": "codex exec --json --sandbox workspace-write 'run tests'",
          "tool": "codex",
          "version": "0.25.0",
          "sandbox": "workspace-write"
        }
      ]
    },
    "authorship": {
      "provider": "git-ai",
      "total_commits": 12,
      "annotated_commits": 8,
      "git_ai": {
        "notes_ref_exists": true,
        "commits_with_notes": 8
      }
    }
  }
}
```

## Key Policy Paths

- `.ai_use.instructions.root.exists` — Any instruction file at repo root
- `.ai_use.instructions.root.filename` — Which file (AGENTS.md, CLAUDE.md, etc.)
- `.ai_use.instructions.root.lines` — Line count for length checks
- `.ai_use.instructions.root.sections` — Section headings for content requirements
- `.ai_use.instructions.total_bytes` — Combined size for context window budget
- `.ai_use.instructions.directories[]` — Per-directory files with symlink status
- `.ai_use.plans_dir.exists` — Dedicated plans directory present
- `.ai_use.cicd.cmds[]` — AI CLI invocations in CI (cmd, tool, version, config flags)
- `.ai_use.cicd.cmds[].tool` — Which tool (claude, codex, gemini)
- `.ai_use.cicd.cmds[].allowed_tools` — Claude: tools allowed without permission
- `.ai_use.cicd.cmds[].sandbox` — Codex/Gemini: sandbox mode
- `.ai_use.cicd.cmds[].approval_mode` — Codex/Gemini: approval mode
- `.ai_use.authorship.total_commits` — Commits in scope
- `.ai_use.authorship.annotated_commits` — Commits with AI annotations
- `.ai_use.authorship.provider` — Detection method (`git-ai` or `trailers`)
