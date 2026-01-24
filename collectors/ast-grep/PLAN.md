# ast-grep Collector Implementation Plan

This document outlines the design for a generic, configurable ast-grep collector that extracts code patterns from repositories and stores them in the Component JSON.

## Goals

1. **Generic & Configurable**: Users define what patterns to search for via YAML rule files
2. **Efficient**: Only store query results, NOT the entire AST (which would be massive for large codebases)
3. **Multi-language**: Support all 20+ languages that ast-grep supports
4. **Structured Output**: Results map cleanly to the `.code_patterns` Component JSON category
5. **Extensible**: Easy for users to add new rules without modifying the collector

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      User Configuration                      │
│                                                              │
│  lunar-config.yml                                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  - uses: ./collectors/ast-grep                        │   │
│  │    with:                                              │   │
│  │      rules: |                                         │   │
│  │        id: security.sql_concat                        │   │
│  │        language: go                                   │   │
│  │        rule:                                          │   │
│  │          pattern: $DB.Query($SQL + $VAR)              │   │
│  │        ---                                            │   │
│  │        id: logging.printf                             │   │
│  │        language: go                                   │   │
│  │        rule:                                          │   │
│  │          pattern: fmt.Printf($$$)                     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ast-grep Collector                         │
│                                                              │
│  1. Write `rules` string to temp YAML file                  │
│  2. Run `ast-grep scan --rule <temp-file> --json .`          │
│  3. Parse JSON output, group matches by ruleId              │
│  4. Map ruleId → category.subcategory for Component JSON    │
│  5. Write to Component JSON via `lunar collect`             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               Component JSON (.code_patterns)                │
│                                                              │
│  {                                                           │
│    "code_patterns": {                                        │
│      "source": {"tool": "ast-grep", "version": "0.38.0"},   │
│      "security": { ... },                                    │
│      "logging": { ... },                                     │
│      "custom": { ... }                                       │
│    }                                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration Model

**Constraint**: Lunar's `with` configuration only supports string values—no file paths or directory references.

### Single `rules` Input

Users provide a **multi-line YAML string** containing all ast-grep rules. This gives full access to ast-grep's rule syntax while staying within Lunar's string-only constraint.

```yaml
collectors:
  - uses: ./collectors/ast-grep
    on: [backend]
    with:
      rules: |
        id: security.sql_concat
        language: go
        message: SQL query built via string concatenation - use parameterized queries
        severity: error
        rule:
          pattern: $DB.Query($SQL + $VAR)
        ---
        id: security.eval
        language: python
        message: Dangerous eval() usage detected
        severity: error
        rule:
          pattern: eval($EXPR)
        ---
        id: logging.printf
        language: go
        message: Use structured logging (slog) instead of fmt.Printf
        severity: warning
        rule:
          pattern: fmt.Printf($$$)
        ---
        id: errors.ignored
        language: go
        message: Error return value is ignored
        severity: warning
        rule:
          all:
            - pattern: $ERR := $FUNC($$$)
            - not:
                follows:
                  pattern: if $ERR != nil { $$$ }
                  stopBy: end
```

**Key points:**
- Uses YAML's `|` literal block scalar for multi-line strings
- Multiple rules separated by `---` (YAML multi-document syntax)
- Full ast-grep syntax available (patterns, `kind`, `has`, `inside`, `all`, `any`, `not`, etc.)
- Rule ID format: `<category>.<subcategory>` maps directly to Component JSON structure

### Rule ID Convention

The rule `id` field determines where results appear in the Component JSON:

| Rule ID | Component JSON Path |
|---------|---------------------|
| `security.sql_concat` | `.code_patterns.security.sql_concat` |
| `security.eval` | `.code_patterns.security.eval` |
| `logging.printf` | `.code_patterns.logging.printf` |
| `errors.ignored` | `.code_patterns.errors.ignored` |

**Format**: `<category>.<subcategory>`

If a rule ID doesn't contain a dot, it goes under `.code_patterns.custom.<rule_id>`.

### ast-grep Rule Fields

Each rule can include standard ast-grep fields:

| Field | Description | Used in Output? |
|-------|-------------|-----------------|
| `id` | Rule identifier (required) | Yes — determines category/subcategory |
| `language` | Target language (required) | No |
| `message` | Human-readable description | Yes — included in each match |
| `severity` | `error`, `warning`, `info`, `hint` | Yes — included in each match |
| `rule` | The matching rule (required) | No |

### Complex Rule Example

Full ast-grep power is available:

```yaml
# Find fmt.Printf only in production code (not test functions)
id: logging.printf_in_prod
language: go
message: Use structured logging (slog) instead of fmt.Printf in production code
severity: warning
rule:
  all:
    - pattern: fmt.Printf($$$)
    - inside:
        kind: function_declaration
        stopBy: end
    - not:
        inside:
          pattern: func Test$NAME($$$) { $$$ }
          stopBy: end
```

---

## Collector Inputs

| Input | Description | Required |
|-------|-------------|----------|
| `rules` | Multi-line YAML string containing ast-grep rules | Yes |
| `exclude_paths` | Comma-separated paths to exclude from scanning | No (default: `vendor,node_modules,.git`) |
| `max_matches_per_rule` | Maximum matches to report per rule | No (default: `100`) |

### Full Example

```yaml
# lunar-config.yml
collectors:
  - uses: ./collectors/ast-grep
    on: [go, python]
    with:
      max_matches_per_rule: 50
      rules: |
        # Security checks
        id: security.sql_concat
        language: go
        message: SQL query built via string concatenation
        severity: error
        rule:
          pattern: $DB.Query($SQL + $VAR)
        ---
        id: security.eval
        language: python
        message: Dangerous eval() usage
        severity: error
        rule:
          pattern: eval($EXPR)
        ---
        # Logging checks
        id: logging.printf
        language: go
        message: Use structured logging instead of fmt.Printf
        severity: warning
        rule:
          pattern: fmt.Printf($$$)
        ---
        # Complex rule with relational matching
        id: errors.ignored_error
        language: go
        message: Error return value is ignored
        severity: warning
        rule:
          kind: short_var_declaration
          has:
            kind: identifier
            regex: ^err$
          not:
            follows:
              pattern: if err != nil { $$$ }
              stopBy: end
```

---

## Output Structure in Component JSON

The collector writes to `.code_patterns` following the established schema in `cat-code-patterns.md`.

### ast-grep JSON Output

For reference, ast-grep's `--json` output looks like:

```json
[
  {
    "ruleId": "security.sql_concat",
    "message": "SQL query built via string concatenation",
    "severity": "error",
    "file": "db/queries.go",
    "range": {
      "start": { "line": 42, "column": 8 },
      "end": { "line": 42, "column": 45 }
    },
    "text": "db.Query(\"SELECT * FROM users WHERE id=\" + userId)"
  }
]
```

### Component JSON Structure

We transform this into the Component JSON format:

```json
{
  "code_patterns": {
    "source": {
      "tool": "ast-grep",
      "version": "0.38.0"
    },
    "<category>": {
      "<subcategory>": {
        "count": 2,
        "message": "Message from rule definition",
        "severity": "error",
        "matches": [
          {
            "file": "path/to/file.go",
            "range": {
              "start": { "line": 42, "column": 8 },
              "end": { "line": 42, "column": 45 }
            },
            "code": "matched code snippet"
          }
        ]
      }
    }
  }
}
```

### Field Mapping

| ast-grep Field | Component JSON Field | Notes |
|----------------|---------------------|-------|
| `ruleId` | Path: `.<category>.<subcategory>` | Split on `.` to determine path |
| `message` | `message` | From rule definition |
| `severity` | `severity` | `error`, `warning`, `info`, `hint` |
| `file` | `matches[].file` | Relative path |
| `range.start.line` | `matches[].range.start.line` | 0-indexed from ast-grep |
| `range.start.column` | `matches[].range.start.column` | 0-indexed from ast-grep |
| `range.end.*` | `matches[].range.end.*` | End position |
| `text` | `matches[].code` | The matched source code |
| (computed) | `count` | Total matches for this rule |

### Example Output

```json
{
  "code_patterns": {
    "source": {
      "tool": "ast-grep",
      "version": "0.38.0"
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

### Aggregation Logic

1. **Group by ruleId**: Split on `.` to get category and subcategory
2. **Count**: Total matches for this rule
3. **Message/Severity**: From rule definition (same for all matches)
4. **Matches**: Array of `{file, range, code}` objects (capped at `max_matches_per_rule`)

Policies can derive "clean" status from `count == 0`.

## Next Steps

1. **Review this plan** — Confirm the `rules` input format and output structure
2. **Implement `main.sh`** — Write rules to temp file, run `ast-grep scan`, parse JSON, aggregate
3. **Create `lunar-collector.yml`** — Define `rules`, `exclude_paths`, `max_matches_per_rule` inputs
4. **Build container image** — Dockerfile/Earthfile with ast-grep binary
5. **Write README** — Document rule format, examples, and best practices
6. **Test** — Validate against sample repos with known patterns
