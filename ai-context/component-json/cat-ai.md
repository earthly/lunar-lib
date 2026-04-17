# Category: `.ai`

AI coding assistant usage — code reviewers, instruction files, plans directories, and authorship annotations.

```json
{
  "ai": {
    "code_reviewers": [
      {
        "tool": "coderabbit",
        "check_name": "coderabbitai",
        "detected": true,
        "last_seen": "2024-01-15T10:30:00Z"
      },
      {
        "tool": "claude",
        "check_name": "claude-code-review",
        "detected": false
      }
    ],
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

## Sources

The `.ai` namespace is populated by multiple collectors working together:

- **[`ai`](../../collectors/ai)** collector — tool-agnostic data: `instructions`, `plans_dir`, `authorship`
- **[`claude`](../../collectors/claude)** collector — appends to `code_reviewers[]` and `instructions.all[]` (CLAUDE.md), adds Claude-specific CI detection
- **[`coderabbit`](../../collectors/coderabbit)** collector — appends to `code_reviewers[]`, adds CodeRabbit config
- **[`codex`](../../collectors/codex)** / **[`gemini`](../../collectors/gemini)** collectors — append their own instruction files and CI invocations

## Key Policy Paths

- `.ai.code_reviewers[]` — Active AI code reviewers (tool, check_name, detected)
- `.ai.code_reviewers[].detected` — Whether this reviewer is currently active on the component
- `.ai.instructions.root.exists` — Any instruction file at repo root
- `.ai.instructions.root.filename` — Which file (AGENTS.md, CLAUDE.md, etc.)
- `.ai.instructions.root.lines` — Line count for length checks
- `.ai.instructions.root.sections` — Section headings for content requirements
- `.ai.instructions.total_bytes` — Combined size for context window budget
- `.ai.instructions.directories[]` — Per-directory files with symlink status
- `.ai.plans_dir.exists` — Dedicated plans directory present
- `.ai.authorship.total_commits` — Commits in scope
- `.ai.authorship.annotated_commits` — Commits with AI annotations
- `.ai.authorship.provider` — Detection method (`git-ai` or `trailers`)
