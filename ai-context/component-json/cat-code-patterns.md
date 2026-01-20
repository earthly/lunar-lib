# Category: `.code_patterns`

AST-based code pattern analysis. These patterns are extracted by analyzing source code structure using tools like ast-grep.

```json
{
  "code_patterns": {
    "source": {
      "tool": "ast-grep",
      "version": "0.25.0"
    },
    "security": {
      "sql_concat": {
        "count": 0,
        "locations": [],
        "clean": true
      },
      "eval_exec": {
        "count": 2,
        "locations": [
          {"file": "utils/dynamic.py", "line": 45},
          {"file": "handlers/admin.py", "line": 112}
        ],
        "clean": false
      },
      "weak_crypto": {
        "count": 1,
        "algorithms": ["md5"],
        "locations": [{"file": "auth/hash.go", "line": 23}]
      },
      "hardcoded_credentials": {
        "count": 0,
        "locations": [],
        "clean": true
      }
    },
    "logging": {
      "printf_violations": {
        "count": 5,
        "locations": [
          {"file": "handler.go", "line": 42, "code": "fmt.Printf(...)"}
        ]
      },
      "uses_structured_logging": false,
      "library": "fmt"
    },
    "errors": {
      "ignored_errors": {
        "count": 3,
        "locations": [{"file": "db.go", "line": 88}]
      },
      "panic_usage": {
        "count": 0,
        "locations": [],
        "panic_free": true
      },
      "all_handled": false
    },
    "http": {
      "missing_timeout": {
        "count": 2,
        "locations": [{"file": "client.go", "line": 15}]
      },
      "all_have_timeout": false
    },
    "metrics": {
      "declared": [
        {
          "type": "counter",
          "name": "http_requests_total",
          "file": "metrics/http.go",
          "line": 23,
          "has_help_text": true
        },
        {
          "type": "histogram",
          "name": "http_request_duration_seconds",
          "file": "metrics/http.go",
          "line": 30,
          "has_help_text": true
        }
      ],
      "count": 8,
      "has_metrics": true,
      "naming_violations": [],
      "follows_conventions": true
    },
    "feature_flags": {
      "library": "launchdarkly",
      "flags": [
        {
          "key": "enable-new-checkout",
          "file": "checkout/handler.go",
          "line": 45,
          "variation_type": "bool"
        }
      ],
      "count": 12,
      "follows_conventions": true
    },
    "lifecycle": {
      "sigterm_handled": true,
      "graceful_shutdown": true,
      "signal_handling": {
        "location": {"file": "main.go", "line": 52}
      }
    },
    "health": {
      "endpoint_implemented": true,
      "endpoint_path": "/healthz",
      "checks_database": true,
      "checks_cache": true,
      "dependency_checks": ["database", "redis"]
    },
    "config": {
      "env_vars": [
        {"name": "DATABASE_URL", "file": "config/db.go", "line": 12},
        {"name": "API_KEY", "file": "config/auth.go", "line": 8}
      ],
      "env_var_count": 15
    },
    "testing": {
      "tests_without_assertions": [],
      "tests_without_assertions_count": 0,
      "all_have_assertions": true,
      "empty_catch_blocks": [],
      "empty_catch_count": 0
    }
  }
}
```

## Key Policy Paths

- `.code_patterns.security.sql_concat.clean` — No SQL injection patterns
- `.code_patterns.security.eval_exec.clean` — No eval/exec usage
- `.code_patterns.security.weak_crypto.count` — Weak crypto usage count
- `.code_patterns.logging.uses_structured_logging` — Structured logging enforced
- `.code_patterns.errors.all_handled` — All errors handled
- `.code_patterns.http.all_have_timeout` — HTTP clients have timeouts
- `.code_patterns.metrics.has_metrics` — Prometheus metrics declared
- `.code_patterns.metrics.follows_conventions` — Metrics follow naming conventions
- `.code_patterns.feature_flags.count` — Feature flag count
- `.code_patterns.lifecycle.sigterm_handled` — SIGTERM handling for graceful shutdown
- `.code_patterns.lifecycle.graceful_shutdown` — Graceful shutdown implemented
- `.code_patterns.health.endpoint_implemented` — Health check in code
- `.code_patterns.testing.all_have_assertions` — Tests have assertions
