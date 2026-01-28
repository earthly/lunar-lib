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
