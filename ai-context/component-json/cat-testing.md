# Category: `.testing`

Test execution results and code coverage. Normalized across frameworks and tools.

```json
{
  "testing": {
    "source": {
      "framework": "go test",
      "integration": "ci"
    },
    "results": {
      "total": 156,
      "passed": 154,
      "failed": 2,
      "skipped": 0
    },
    "failures": [
      {
        "name": "TestPaymentValidation",
        "file": "payment_test.go",
        "line": 42,
        "message": "expected 200, got 400"
      }
    ],
    "all_passing": false,
    "runs": [
      {
        "pipeline": "CI",
        "run_id": "36909154652",
        "attempt": 1,
        "job": "test",
        "step": 4,
        "total": 156,
        "passed": 154,
        "failed": 2,
        "skipped": 0,
        "all_passing": false
      }
    ],
    "coverage": {
      "source": {
        "tool": "go cover",
        "integration": "ci"
      },
      "percentage": 85.5,
      "lines": {
        "covered": 1200,
        "total": 1404
      },
      "files": [
        {
          "path": "payment.go",
          "percentage": 92.0
        }
      ]
    }
  }
}
```

## Key Policy Paths

- `.testing` — Tests executed (use `assert_exists(".testing")`)
- `.testing.results.failed` — Failure count
- `.testing.all_passing` — Clean test run (the last build to finish at the commit)
- `.testing.runs[]` — One entry per build. Arrays concatenate across builds, so a policy can require every build to pass; group by `run_id`, `job` and `step` and keep the highest `attempt` so a re-run replaces its own earlier attempt
- `.testing.coverage` — Coverage collected (use `assert_exists(".testing.coverage")`)
- `.testing.coverage.percentage` — Overall coverage (policy compares against threshold)
