# Repository Guardrails

Enforce repository hygiene standards for README, CODEOWNERS, and standard configuration files.

## Overview

Validates that repositories maintain documentation standards, code ownership rules, and include standard configuration files. Consolidates the existing `readme` and `codeowners` policies into a single plugin, adding checks for .gitignore, LICENSE, SECURITY.md, CONTRIBUTING.md, and .editorconfig.

## Policies

This plugin provides the following policies (use `include` to select a subset):

### README Checks

| Policy | Description |
|--------|-------------|
| `readme-exists` | Verifies a README file exists in the repository |
| `readme-min-line-count` | Requires README to have minimum line count (default 25) |
| `readme-required-sections` | Ensures README contains required section headings |

### CODEOWNERS Checks

| Policy | Description |
|--------|-------------|
| `codeowners-exists` | Requires a CODEOWNERS file in the repository |
| `codeowners-valid` | Validates CODEOWNERS syntax (owner formats) |
| `codeowners-catchall` | Requires a default catch-all rule (*) |
| `codeowners-min-owners` | Minimum owners per rule (default 2) |
| `codeowners-team-owners` | Requires at least one team-based owner |
| `codeowners-no-individuals-only` | Each rule must include a team owner |
| `codeowners-no-empty-rules` | Flags rules with no owners assigned |
| `codeowners-max-owners` | Maximum owners per rule (default 10) |

### Standard File Checks

| Policy | Description |
|--------|-------------|
| `gitignore-exists` | Verifies .gitignore file exists |
| `license-exists` | Verifies LICENSE file exists |
| `security-md-exists` | Verifies SECURITY.md file exists |
| `contributing-md-exists` | Verifies CONTRIBUTING.md file exists |
| `editorconfig-exists` | Verifies .editorconfig file exists (**disabled by default**) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.repo.readme` | object | `repo` collector (readme subcollector) |
| `.repo.files` | object | `repo` collector (repo-files subcollector) |
| `.ownership.codeowners` | object | `repo` collector (codeowners subcollector) |

**Note:** Ensure the `repo` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/repo@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [readme-exists, codeowners-exists, gitignore-exists, license-exists]
    # with:
    #   min_lines: "25"
    #   required_sections: "Installation,Usage"
    #   min_owners_per_rule: "2"
    #   max_owners_per_rule: "10"
    #   check_editorconfig: "true"
```

## Examples

### Passing Example

```json
{
  "repo": {
    "readme": {
      "exists": true,
      "path": "README.md",
      "lines": 150,
      "sections": ["Installation", "Usage", "Contributing"]
    },
    "files": {
      "gitignore": true,
      "license": true,
      "security_md": true,
      "contributing": true,
      "editorconfig": true
    }
  },
  "ownership": {
    "codeowners": {
      "exists": true,
      "valid": true,
      "errors": [],
      "team_owners": ["@acme/platform-team"],
      "rules": [
        { "pattern": "*", "owners": ["@acme/platform-team"], "owner_count": 1 }
      ]
    }
  }
}
```

### Failing Example

```json
{
  "repo": {
    "readme": { "exists": false },
    "files": {
      "gitignore": false,
      "license": false,
      "security_md": false,
      "contributing": false,
      "editorconfig": false
    }
  },
  "ownership": {
    "codeowners": { "exists": false }
  }
}
```

**Failure messages:**
- `"README file not found"`
- `"No CODEOWNERS file found"`
- `".gitignore file not found"`
- `"LICENSE file not found"`

## Remediation

When this policy fails, resolve it by adding the missing files:

1. **README** - Add a `README.md` with project description, installation, and usage instructions
2. **CODEOWNERS** - Add a `CODEOWNERS` file (root, `.github/`, or `docs/`) with ownership rules
3. **.gitignore** - Add a `.gitignore` appropriate for your language/framework
4. **LICENSE** - Add a `LICENSE` file with your project's license
5. **SECURITY.md** - Add a `SECURITY.md` with vulnerability disclosure instructions
6. **CONTRIBUTING.md** - Add a `CONTRIBUTING.md` with contribution guidelines
