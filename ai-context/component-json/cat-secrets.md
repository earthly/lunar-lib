# Category: `.secrets`

Secret/credential scanning. **Normalized across Gitleaks, TruffleHog, detect-secrets, etc.**

```json
{
  "secrets": {
    "source": {
      "tool": "gitleaks",
      "version": "8.18.0",
      "integration": "ci"
    },
    "issues": [
      {
        "rule": "generic-api-key",
        "file": "config/settings.py",
        "line": 42,
        "secret_type": "Generic API Key"
      }
    ],
    "native": {
      "gitleaks": {
        "auto": {
          "report": [
            {
              "RuleID": "generic-api-key",
              "File": "config/settings.py",
              "StartLine": 42,
              "Secret": "REDACTED",
              "Match": "api_key = 'REDACTED'"
            }
          ]
        }
      }
    }
  }
}
```

Collectors also ship the scanner's raw output under `.secrets.native.<tool>`.
The credential is masked there — see
[Never store the detected credential](#never-store-the-detected-credential)
below, which is a hard requirement for any collector writing to this category.

## Issue Schema

Each entry in `.secrets.issues[]` has:

| Field | Type | Description |
|-------|------|-------------|
| `rule` | string | Scanner rule ID (e.g. `generic-api-key`, `aws-access-key-id`) |
| `file` | string | Relative path to file containing the secret |
| `line` | integer | Line number of the finding |
| `secret_type` | string | Human-readable secret type |

## Key Policy Paths

- `.secrets` — Secret scan executed (use `assert_exists(".secrets")`)
- `.secrets.issues[]` — Array of detected secrets (empty = clean)

## Never store the detected credential

**This category describes secrets that were found. It must never contain the
secret itself.** The normalized `issues` schema above is safe by construction —
it carries only rule, file, line, and type. The trap is the raw
`.secrets.native.<tool>` path that collectors ship alongside it: secret
scanners put the live credential in their raw output by default, and everything
written to Component JSON is persisted server-side and is readable by anyone
with access to the datasource.

Any collector writing to `.secrets` **must** mask the credential before it
reaches `lunar collect`, and must **fail closed** — if masking cannot be
verified, drop the raw output rather than shipping it unmasked. Losing raw
detail degrades a debugging aid; shipping it unmasked writes a live credential
into the database.

| Tool | Fields carrying the credential | How to mask |
|------|-------------------------------|-------------|
| Gitleaks | `.Secret`, `.Match` | Pass `--redact` when we invoke it; strip both fields with `jq` when the report comes from someone else's command |

Two distinct cases, because they need different fixes:

- **We run the scanner** — use its redaction flag. Verify it actually applied
  (Gitleaks' `--redact` help text only promises "logs and stdout", though it
  does redact the report file too) and treat an unredacted report as a failure.
- **We collect someone else's report** (a CI-hook collector reading a report
  produced by the user's own command) — there is no flag to add, so strip the
  secret-bearing fields yourself. Only collect output whose shape you
  recognize; an unrecognized format may carry the secret in a field you did not
  strip.
