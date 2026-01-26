# `ast-grep` Collector

Extracts code patterns from source code using AST-based analysis with [ast-grep](https://ast-grep.github.io/).

## Overview

This collector runs user-defined ast-grep rules against source code and records pattern matches in the Component JSON. It supports ast-grep's full rule syntax including relational rules (`inside`, `has`), composite rules (`all`, `any`, `not`), and metavariables (`$VAR`, `$$$ARGS`). Results are organized by category and subcategory based on the rule ID.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.code_patterns.source` | object | Tool metadata (name, version) |
| `.code_patterns.<category>.<subcategory>` | object | Matches for each rule, grouped by rule ID |

The rule `id` field determines the Component JSON path. Use the format `<category>.<subcategory>`:

| Rule ID | Component JSON Path |
|---------|---------------------|
| `security.sql_concat` | `.code_patterns.security.sql_concat` |
| `logging.printf` | `.code_patterns.logging.printf` |
| `errors.ignored` | `.code_patterns.errors.ignored` |

If a rule ID doesn't contain a dot, it goes under `.code_patterns.custom.<rule_id>`.

<details>
<summary>Example Component JSON output</summary>

```json
{
  "code_patterns": {
    "source": {
      "tool": "ast-grep",
      "version": "0.40.5"
    },
    "security": {
      "sql_concat": {
        "count": 0,
        "message": "SQL query built via string concatenation",
        "severity": "error",
        "matches": []
      },
      "eval": {
        "count": 2,
        "message": "Dangerous eval() usage",
        "severity": "error",
        "matches": [
          {
            "file": "utils/dynamic.py",
            "range": { "start": { "line": 45, "column": 8 }, "end": { "line": 45, "column": 25 } },
            "code": "eval(user_input)"
          },
          {
            "file": "handlers/admin.py",
            "range": { "start": { "line": 112, "column": 12 }, "end": { "line": 112, "column": 30 } },
            "code": "exec(code_string)"
          }
        ]
      }
    },
    "logging": {
      "printf": {
        "count": 5,
        "message": "Use structured logging instead of fmt.Printf",
        "severity": "warning",
        "matches": [
          {
            "file": "handler.go",
            "range": { "start": { "line": 42, "column": 2 }, "end": { "line": 42, "column": 38 } },
            "code": "fmt.Printf(\"User: %s\", user)"
          }
        ]
      }
    }
  }
}
```

</details>

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `rules` | Yes | - | Multi-line YAML string containing ast-grep rules. Use YAML multi-document syntax (`---`) to define multiple rules. See [ast-grep.github.io](https://ast-grep.github.io/) for rule syntax. |
| `exclude_paths` | No | `vendor,node_modules,.git,dist,build` | Comma-separated paths to exclude from scanning |
| `max_matches_per_rule` | No | `100` | Maximum matches to report per rule |
| `debug` | No | `false` | Enable debug output (echoes rules and raw ast-grep output) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ast-grep@v1.0.0
    on: [go, python]
    with:
      rules: |
        id: logging.logrus_fatal
        language: go
        message: Found logrus.Fatal - consider error handling instead
        severity: warning
        rule:
          kind: call_expression
          regex: "^logrus\\.Fatal"
        ---
        id: http.hardcoded_port
        language: go
        message: Hardcoded port in ListenAndServe
        severity: warning
        rule:
          kind: call_expression
          regex: "^http\\.ListenAndServe"
        ---
        id: security.eval
        language: python
        message: Dangerous eval() usage
        severity: error
        rule:
          pattern: eval($EXPR)
      # exclude_paths: "vendor,node_modules,.git,dist,build"
      # max_matches_per_rule: "100"
      # debug: "false"
```

## Related Policies

None.
