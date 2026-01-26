# Codecov

Detects Codecov usage and fetches coverage results from the Codecov API.

## Overview

This collector detects when Codecov runs in CI and fetches coverage results from the Codecov API. It triggers on codecov commands via the `ci-after-command` hook and records both that codecov ran and the coverage results from the API.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.testing.codecov.detected` | boolean | `true` when codecov ran |
| `.testing.codecov.uploaded` | boolean | `true` when codecov upload was detected |
| `.testing.codecov.results` | object | Coverage results from Codecov API |

See the example below for the full structure.

<details>
<summary>Example Component JSON output</summary>

```json
{
  "testing": {
    "codecov": {
      "detected": true,
      "uploaded": true,
      "results": {
        "coverage": 85.5
      }
    }
  }
}
```

</details>

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `ran` | Records that codecov ran |
| `results` | Fetches coverage results from Codecov API |

Both collectors use hook type `ci-after-command` with pattern `codecov(cli)?|bash.*codecov`.

The `results` collector:
1. Detects upload commands (`upload`, `do-upload`, `upload-process`, or commands with `-t`/`-f` flags)
2. Records that an upload was detected (`.testing.codecov.uploaded`)
3. Fetches coverage from the Codecov API using `LUNAR_SECRET_CODECOV_API_TOKEN`

## Inputs

This collector has no configurable inputs.

## Secrets

- `CODECOV_API_TOKEN` - Codecov API token for fetching coverage results (required for the `results` collector)

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codecov@main
    on: [backend]
    # include: [ran]  # Only record that codecov ran (no API call needed)
```

To fetch coverage results, configure the `CODECOV_API_TOKEN` secret in your Lunar configuration.

## Related Policies

- [`codecov`](https://github.com/earthly/lunar-lib/tree/main/policies/codecov) - Validates Codecov usage and coverage thresholds
