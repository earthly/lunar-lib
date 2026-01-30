# Category: `.repo`

Repository structure, README, and standard files.

```json
{
  "repo": {
    "readme": {
      "exists": true,
      "path": "README.md",
      "lines": 150,
      "sections": ["Installation", "Usage", "API", "Contributing"]
    },
    "files": {
      "gitignore": true,
      "dockerignore": true,
      "editorconfig": false,
      "license": true,
      "contributing": true,
      "makefile": true
    },
    "license": {
      "type": "MIT",
      "path": "LICENSE"
    },
    "languages": {
      "primary": "go",
      "all": ["go", "python", "shell"]
    }
  }
}
```

## Key Policy Paths

- `.repo.readme.exists` — README present
- `.repo.readme.path` — Which README file was found
- `.repo.readme.sections` — Section headings for content requirements
- `.repo.files.<name>` — Standard file presence
- `.repo.languages.primary` — Primary language detection
