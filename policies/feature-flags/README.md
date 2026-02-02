# Feature Flags Policies

Enforces feature flag hygiene by detecting flags that have exceeded their expected lifespan.

## Overview

This policy plugin helps teams manage feature flag lifecycle by identifying flags that have existed longer than a configurable threshold. Feature flags should be temporary—once a feature is fully rolled out and stable, the flag should be removed. Stale feature flags add unnecessary complexity, increase cognitive load, and contribute to technical debt.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `feature-flags-age` | Detects feature flags older than threshold | Feature flag has existed too long and should be cleaned up |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.code_patterns.feature_flags` | object | [`ast-grep`](https://github.com/earthly/lunar-lib/tree/main/collectors/ast-grep) collector |
| `.code_patterns.feature_flags.flags` | array | [`ast-grep`](https://github.com/earthly/lunar-lib/tree/main/collectors/ast-grep) collector |
| `.code_patterns.feature_flags.flags[].key` | string | [`ast-grep`](https://github.com/earthly/lunar-lib/tree/main/collectors/ast-grep) collector |
| `.code_patterns.feature_flags.flags[].file` | string | [`ast-grep`](https://github.com/earthly/lunar-lib/tree/main/collectors/ast-grep) collector |
| `.code_patterns.feature_flags.flags[].line` | number | [`ast-grep`](https://github.com/earthly/lunar-lib/tree/main/collectors/ast-grep) collector |
| `.code_patterns.feature_flags.flags[].created_at` | number (Unix timestamp) | [`ast-grep`](https://github.com/earthly/lunar-lib/tree/main/collectors/ast-grep) collector |

**Note:** Ensure the corresponding collector is configured before enabling this policy. The collector must provide feature flag metadata including creation timestamps (e.g., via git blame).

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/feature-flags@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, frontend]
    enforcement: report-pr      # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    # include: [feature-flags-age]  # Only run specific checks (omit to run all)
    # with:
    #   max_days: "60"  # Override default 90-day threshold
```

## Examples

### Passing Example

Feature flags within the allowed age threshold:

```json
{
  "code_patterns": {
    "feature_flags": {
      "library": "launchdarkly",
      "flags": [
        {
          "key": "new_checkout_flow",
          "file": "src/checkout/index.ts",
          "line": 42,
          "created_at": 1735689600
        },
        {
          "key": "dark_mode_beta",
          "file": "src/theme/provider.tsx",
          "line": 15,
          "created_at": 1733097600
        }
      ],
      "count": 2
    }
  }
}
```

All flags are less than 90 days old (default threshold), so the check passes.

### Failing Example

Feature flag that has exceeded the age threshold:

```json
{
  "code_patterns": {
    "feature_flags": {
      "library": "launchdarkly",
      "flags": [
        {
          "key": "legacy_payment_system",
          "file": "src/payments/processor.ts",
          "line": 128,
          "created_at": 1704067200
        }
      ],
      "count": 1
    }
  }
}
```

**Failure message:** `"Feature flag 'legacy_payment_system' at src/payments/processor.ts:128 is 395 days old (max: 90 days)"`

## Remediation

When this policy fails, you should:

1. **Review the feature flag**: Determine if the feature is fully rolled out and stable
2. **Remove the flag**: If the feature is complete, remove the flag and associated conditional logic
3. **Extend if needed**: If the flag is still necessary, consider whether the threshold should be adjusted via configuration, or document why the flag needs to remain
4. **Clean up dead code**: Remove any code paths that were only used during the rollout

### Example cleanup

Before (with flag):

```typescript
if (featureFlags.isEnabled('new_checkout_flow')) {
  return <NewCheckout />;
} else {
  return <LegacyCheckout />;
}
```

After (flag removed):

```typescript
return <NewCheckout />;
```

### Adjusting the threshold

If your team needs a different default threshold, configure it in `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/feature-flags@v1.0.0
    on: ["all"]
    enforcement: block-pr
    with:
      max_days: "120"  # Allow flags up to 120 days old
```

