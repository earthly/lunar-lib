# README Policies

Enforces README best practices including file existence, minimum content length, and required sections.

## Overview

This policy plugin validates README files against common documentation standards. It ensures repositories have proper documentation by checking for file existence, minimum content length, and required section headings. These policies help maintain consistent documentation quality across your organization.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `readme-exists` | Ensures README file exists in the repository root | README file not found |
| `readme-min-line-count` | Ensures README file meets minimum line count | README file has fewer lines than required |
| `readme-required-sections` | Ensures README file contains required section headings | README file is missing one or more required sections |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.repo.readme.exists` | boolean | [`readme`](https://github.com/earthly/lunar-lib/tree/main/collectors/readme) collector |
| `.repo.readme.lines` | number | [`readme`](https://github.com/earthly/lunar-lib/tree/main/collectors/readme) collector |
| `.repo.readme.sections[]` | array | [`readme`](https://github.com/earthly/lunar-lib/tree/main/collectors/readme) collector |

**Note:** Ensure the corresponding collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/readme@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, kubernetes]
    enforcement: report-pr      # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    # include: [readme-exists]  # Only run specific checks (omit to run all)
    # with:                     # Uncomment if inputs are needed
    #   min_lines: 50
    #   required_sections: "Installation,Usage,Contributing"
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
      "sections": [
        "Installation",
        "Usage",
        "API",
        "Contributing",
        "License"
      ]
    }
  }
}
```

This example passes all three policies when configured with:
- `min_lines: "50"`
- `required_sections: "Installation,Usage,Contributing"`

### Failing Examples

#### README file doesn't exist (fails `readme-exists`)

```json
{
  "repo": {
    "readme": {
      "exists": false
    }
  }
}
```

**Failure message:** `"README file not found (expected README.md or README)"`

#### README file has too few lines (fails `readme-min-line-count`)

```json
{
  "repo": {
    "readme": {
      "exists": true,
      "path": "README.md",
      "lines": 25,
      "sections": ["Installation", "Usage"]
    }
  }
}
```

**Failure message:** `"README file has 25 lines, but minimum required is 50"`

#### README file missing required sections (fails `readme-required-sections`)

```json
{
  "repo": {
    "readme": {
      "exists": true,
      "path": "README.md",
      "lines": 150,
      "sections": [
        "Installation",
        "Usage"
      ]
    }
  }
}
```

**Failure message:** `"README file is missing required sections: Contributing"`

## Remediation

### readme-exists

Create a README file (README.md or README) in the repository root:

```markdown
# Project Name

Description of your project.

## Installation

...

## Usage

...
```

### readme-min-line-count

Add more content to your README file to meet the minimum line count requirement. Consider adding:
- Detailed installation instructions
- Usage examples
- Configuration options
- API documentation
- Contributing guidelines
- License information

### readme-required-sections

Add the missing required section headings to your README file. Section headings should use markdown header syntax (`#`, `##`, `###`, etc.). For example:

```markdown
# Project Name

## Installation

...

## Usage

...

## Contributing

...
```

Section matching is case-insensitive, so "Installation", "installation", and "INSTALLATION" all match the required section "Installation".

