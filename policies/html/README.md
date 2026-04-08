# HTML/CSS Guardrails

Enforces HTML and CSS code quality via HTMLHint and Stylelint.

## Overview

Validates that HTML and CSS-family files pass lint checks. Uses data collected by the `html` collector's `htmlhint` and `stylelint` sub-collectors. Checks are configurable with maximum warning thresholds.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `htmlhint-clean` | HTMLHint warnings below threshold | HTML files have lint issues (unclosed tags, missing attributes, etc.) |
| `stylelint-clean` | Stylelint warnings below threshold | CSS/SCSS/LESS files have lint issues (invalid properties, formatting, etc.) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.html` | object | [`html`](https://github.com/earthly/lunar-lib/tree/main/collectors/html) collector |
| `.lang.html.lint.warnings` | array | [`html`](https://github.com/earthly/lunar-lib/tree/main/collectors/html) collector (`htmlhint`) |
| `.lang.html.native.htmlhint` | object | [`html`](https://github.com/earthly/lunar-lib/tree/main/collectors/html) collector (`htmlhint`) |
| `.lang.css` | object | [`html`](https://github.com/earthly/lunar-lib/tree/main/collectors/html) collector |
| `.lang.css.lint.warnings` | array | [`html`](https://github.com/earthly/lunar-lib/tree/main/collectors/html) collector (`stylelint`) |
| `.lang.css.native.stylelint` | object | [`html`](https://github.com/earthly/lunar-lib/tree/main/collectors/html) collector (`stylelint`) |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/html@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [htmlhint-clean]  # Only run specific checks
    with:
      max_htmlhint_warnings: "0"    # Maximum HTMLHint warnings (default: "0")
      max_stylelint_warnings: "0"   # Maximum Stylelint warnings (default: "0")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "html": {
      "file_count": 5,
      "lint": {
        "warnings": []
      },
      "native": {
        "htmlhint": {
          "passed": true,
          "error_count": 0,
          "warning_count": 0
        }
      }
    },
    "css": {
      "file_count": 3,
      "lint": {
        "warnings": []
      },
      "native": {
        "stylelint": {
          "passed": true,
          "error_count": 0,
          "warning_count": 0
        }
      }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "html": {
      "file_count": 5,
      "lint": {
        "warnings": [
          { "file": "index.html", "line": 15, "severity": "warning", "message": "Tag must be paired, missing: </div>", "rule": "tag-pair" }
        ]
      },
      "native": {
        "htmlhint": {
          "passed": false,
          "error_count": 0,
          "warning_count": 1
        }
      }
    },
    "css": {
      "file_count": 3,
      "lint": {
        "warnings": [
          { "file": "styles/main.css", "line": 42, "severity": "error", "message": "Unexpected unknown property \"colr\"", "rule": "property-no-unknown" }
        ]
      },
      "native": {
        "stylelint": {
          "passed": false,
          "error_count": 1,
          "warning_count": 0
        }
      }
    }
  }
}
```

**Failure messages:**
- `"1 HTMLHint warning(s) found, maximum allowed is 0. Run 'htmlhint' and fix all issues."`
- `"1 Stylelint error(s) found, maximum allowed is 0. Run 'stylelint' and fix all issues."`

## Remediation

### htmlhint-clean
1. Run `npx htmlhint **/*.html` to see all warnings
2. Fix the reported issues (unclosed tags, missing attributes, etc.)
3. Configure `.htmlhintrc` to customize rules for your project
4. If more warnings are acceptable, increase `max_htmlhint_warnings` threshold

### stylelint-clean
1. Run `npx stylelint "**/*.{css,scss,less}"` to see all warnings
2. Fix the reported issues (invalid properties, formatting problems, etc.)
3. Configure `.stylelintrc.json` to customize rules for your project
4. If more warnings are acceptable, increase `max_stylelint_warnings` threshold
