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
      "meets_threshold": true,
      "threshold": 80,
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
- `.testing.all_passing` — Clean test run
- `.testing.coverage` — Coverage collected (use `assert_exists(".testing.coverage")`)
- `.testing.coverage.percentage` — Overall coverage
- `.testing.coverage.meets_threshold` — Above minimum
