# CI Archive Collector

Archives completed CI workflow runs and their logs to S3.

## Overview

Once every CI workflow run for a commit has finished, this collector lists those
runs, downloads each one's log archive, bundles them into a single zip, and
uploads it to S3. A receipt under `.ci.archive` records the object URI and an
inventory of what was captured, so consumers can locate the archive without
reconstructing the key. Useful when CI logs need to outlive the provider's
retention window — audit trails, incident forensics, or compliance evidence.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ci.archive.source` | object | Tool, integration, `collected_at`, `collected_sha` |
| `.ci.archive.uri` | string | Full `s3://` URI of the uploaded archive |
| `.ci.archive.bucket` | string | Destination bucket |
| `.ci.archive.key` | string | Object key within the bucket |
| `.ci.archive.size_bytes` | number | Size of the uploaded zip |
| `.ci.archive.run_count` | number | Number of workflow runs included |
| `.ci.archive.runs[]` | array | Archived runs: id, name, workflow `path`, `event`, attempt, status, conclusion, timestamps, `html_url`, `log_bytes` |
| `.ci.archive.errors[]` | array | Runs that could not be archived, with a reason |

Nothing is written when the commit has no completed workflow runs, or when
`s3_bucket` or `GH_TOKEN` is unset — the collector exits 0 with a message on
stderr. If runs exist but nothing is uploaded (every log download failed, or the
archive hit `max_archive_mb`), only `errors` and `source` are written, so
`.ci.archive.uri` is present exactly when an archive exists.

### Archive layout

One object per (component, commit), keyed
`<s3_prefix>/<component-id>/<sha>/<UTC timestamp>.zip`. Inside:

```text
manifest.json          # run inventory, same shape as .ci.archive.runs[]
runs/<run-id>/logs.zip # the provider's log archive, verbatim
```

Logs are stored as the provider returns them rather than being re-packed, so the
per-job file structure is whatever GitHub produced.

## Collectors

| Collector | Description |
|--------|-------------|
| `workflow-logs` | Lists the commit's workflow runs, downloads their logs, uploads one zip to S3 |

### When it runs

It fires at the **doneness gate** — the point at which every workflow run
relevant to a (component, commit) has completed. That is deliberately not a
per-job hook: a job-scoped hook runs while the workflow is still in flight, when
the run's logs are neither complete nor downloadable.

The manifest declares `after-json` and `missing-json` on the same path. A
collector fires if *any* of its hooks match, and these two are complements, so
the pair fires exactly once per cycle regardless of whether `.ci` is populated.
The path is not a real precondition — it is how a path-less "workflow end"
trigger is expressed today.

Two consequences worth knowing:

- **Granularity is per commit, not per run.** The collector fires once after
  *all* runs for the commit finish and archives them together. It does not fire
  once per workflow run.
- **Re-runs are not backfilled.** Runs are resolved from the commit at archive
  time, so a re-run landing after the upload is not retroactively included; the
  next doneness cycle writes a new object under a new timestamp.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ci-archive@v1.0.0
    on: ["domain:your-domain"]
    with:
      s3_bucket: "your-ci-archive-bucket"
      s3_prefix: "lunar/ci-archive"
      aws_region: "us-east-1"
```

Inputs and secrets are documented in `lunar-collector.yml`. `GH_TOKEN` needs
`actions:read`.

AWS credentials resolve like the backstage collector's: an IAM role attached to
the snippet pod first (IRSA, EKS Pod Identity, ECS task role, EC2 instance
profile), then the `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` secrets. Lunar
secrets are shared by every collector, so an attached role always wins over
keys set for another plugin. With `s3_endpoint_url`, only the static keys are
used. The identity needs `s3:PutObject` on the key prefix.

### Limits

- **GitHub only for now.** Run and log retrieval uses the GitHub Actions API;
  other providers need their own log-download path.
- **Log retention.** GitHub deletes run logs after the repository's retention
  period (90 days by default). A run whose logs have already expired is recorded
  in `.ci.archive.errors[]` rather than failing the collection.
- **Size.** Log archives for a busy repository can be large; `max_archive_mb`
  bounds what gets uploaded.
- **Monorepos.** Runs are resolved per commit, not per component, so each
  component in a monorepo archives every run at the commit under its own key.
