# CI Archive Collector

Archives completed CI workflow runs and their logs to S3.

## Overview

Each time a CI workflow run on the default branch finishes, re-runs included,
this collector downloads that run attempt's logs, bundles them with the run and
its jobs, and uploads the zip to S3. It appends a receipt to `.ci.archive.runs`
saying where the archive went, so consumers can find it without reconstructing
the key. Useful when CI logs need to outlive the provider's retention window:
audit trails, incident forensics, or compliance evidence.

A daily pass backs up any run the per-run path missed; see
[Daily backup](#daily-backup).

It can also run in your own CI as a GitHub Action, writing the same receipts
and objects with your runners' credentials; see
[From your own CI](#from-your-own-ci).

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ci.archive.runs[]` | array | One entry per archived run attempt: `uri`, `bucket`, `key`, `size_bytes`, run `id`, `attempt`, `name`, workflow `path`, `event`, `head_branch`, `head_sha`, `conclusion`, `started_at`, `completed_at`, `html_url`, `log_bytes`, `log_lines`, `jobs[]` (name, conclusion), `source`; for a run another workflow started, also `triggered_by_run_id` and `origin_source` |
| `.ci.archive.backup` | object | The last daily backup pass, on the repository's root component: `branch`, `since`, `until`, `attempt_count` (run attempts checked), `uploaded_count` (attempts it had to upload; absent without `s3_bucket`), `source` |

Nothing is written when `GH_TOKEN` is unset, when the workflow doesn't match
`include_runs_pattern`, or when the run's event isn't in `include_events`: the
collector exits 0 with a message on stderr. A run that can't be archived (logs
gone, over `max_archive_mb`, S3 rejected the upload, or no role in
`aws_assume_role_arns` could be assumed) fails the collector run and writes
nothing.

### Archive layout

One object per run attempt, keyed
`<s3_prefix>/<host>/<owner>/<repo>/<sha>/<run-id>-<attempt>.zip`. Inside:

```text
manifest.json   # the run and its jobs, with steps
logs.zip        # GitHub's log archive for the attempt, verbatim
```

A run that never started a job, such as one whose workflow file GitHub couldn't
parse, has no logs, so its object holds only `manifest.json`.

## Collectors

| Collector | Description |
|--------|-------------|
| `backup-logs-s3` | Archives each finished run attempt to S3 and records it |
| `backup-logs-s3-daily` | Once a day, uploads any recent run attempt that isn't in S3 yet |

### When it runs

On the Hub's `after-ci-pipeline` hook: once per finished run attempt on the
default branch, for each component the run's commit belongs to, after the
attempt's logs exist. PR runs aren't archived. A re-run is a new attempt and is
archived again. Component checks don't wait for it.

It needs a Hub that has the `after-ci-pipeline` hook. In a monorepo, set
[`ciPipelines`](https://docs-lunar.earthly.dev/configuration/lunar-config/components#cipipelines)
on components to say which workflows are theirs.

Runs started by `schedule` or `workflow_dispatch` are filed at the branch head
when they started. To archive only runs a commit started, set
`include_events: push`.

### Runs started by another workflow

GitHub runs a workflow triggered `on: workflow_run`, such as a promote or smoke
test after a deploy, at the default branch's latest commit rather than the commit
its chain started from. On a busy main, those runs would be archived under a
later commit than the one they deployed.

So the Hub follows the chain back to its first run and archives each run under
that run's commit. It learns each link from the CI Tracer, which reads the run
that triggered a job's run from the job's event payload and reports it when the
job starts. Where no tracer runs, the workflow can name that run in its title,
and the Hub reads the link from there:

```yaml
run-name: "${{ github.workflow }} (from run ${{ github.event.workflow_run.id }})"
```

The receipt keeps GitHub's commit in `head_sha`, adds `triggered_by_run_id`, and
records how the link was found in `origin_source`: `tracer`, `run-name`, or
`unresolved` when nothing linked the run and it was archived at GitHub's commit.

This works with GitHub Actions only, for now. It needs a Hub with chained-run
following turned on (`HUB_CHAINED_RUNS_ENABLED=true`, off by default); see
[runs started by another pipeline](https://docs-lunar.earthly.dev/configuration/lunar-config/collector-hooks#runs-started-by-another-pipeline).

### Daily backup

`backup-logs-s3-daily` runs at 04:00 UTC, or on the cron schedule in
`daily_backup_schedule`. It lists the default branch's
finished runs created in the last `daily_backup_lookback_hours` (48), and
uploads every run attempt whose object isn't in the bucket yet, keyed as above.
It's the safety net for runs the per-run path missed, such as a skipped hook or
a Hub restart. It adds nothing to `.ci.archive.runs`, and writes a summary of
the pass to `.ci.archive.backup`.

- In a monorepo, target only the root component (`github.com/<owner>/<repo>`):
  it captures workflows for the entire repository, unlike `backup-logs-s3`,
  which can tell subcomponents' runs apart. On a subdirectory component it
  exits without doing anything.
- It checks every commit folder the window's runs built, so a chained run the
  Hub archived under its chain's first commit counts as present. Runs it
  uploads itself are keyed by the commit GitHub recorded.
- Each run is in two passes' windows, so a run still going at one pass is backed
  up by the next. On a custom schedule, keep the lookback at least twice its
  interval. A re-run of a run created before the window isn't seen; raise the
  lookback to cover it.
- `include_runs_pattern` and `include_events` apply here too.
- A run attempt it can't archive fails the pass once the others are done, and
  the next pass tries it again.

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

In a monorepo, import it a second time so the daily backup targets only the root
component:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ci-archive@v1.0.0
    on: ["domain:your-domain"]
    exclude: [backup-logs-s3-daily]
    with:
      s3_bucket: "your-ci-archive-bucket"
  - uses: github://earthly/lunar-lib/collectors/ci-archive@v1.0.0
    name: ci-archive-daily
    on: ["component:github.com/acme/monorepo"]
    include: [backup-logs-s3-daily]
    with:
      s3_bucket: "your-ci-archive-bucket"
```

Inputs and secrets are documented in `lunar-collector.yml`. `GH_TOKEN` needs
`actions:read`.

AWS credentials resolve like the backstage collector's: an IAM role attached to
the snippet pod first (IRSA, EKS Pod Identity, ECS task role, EC2 instance
profile), then the `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` secrets. Lunar
secrets are shared by every collector, so an attached role always wins over
keys set for another plugin. With `s3_endpoint_url`, only the static keys are
used. The identity needs `s3:PutObject` on the key prefix, and the daily backup
also needs `s3:ListBucket` on it.

For a bucket in another account, set `aws_assume_role_arns` to a role there that
can write to it. The collector assumes that role with the credentials above,
sending `aws_external_id` if set, and uploads as the role. Its trust policy must
allow the snippet pod's role, and the pod's role needs `sts:AssumeRole` on it.
STS sessions are named `lunar-ci-archive-<run-id>-<attempt>`, so the bucket
account's CloudTrail shows which run each upload came from.

### Try it without S3

Leave out `s3_bucket` to check which runs fire, and on which commits, before
wiring up a bucket. Each run is still recorded, with its log's size and line
count, but nothing is uploaded and no AWS credentials are needed. `GH_TOKEN` is
still required, to read the run and its logs. Without a bucket, the daily
backup only counts the run attempts in its window.

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ci-archive@v1.0.0
    on: ["domain:your-domain"]
```

Once a workflow run finishes, its entry shows up under `.ci.archive.runs` in the
Component JSON of the commit it ran on, for example with
`lunar component get-json <component> --git-sha <sha>`. Abridged:

```json
{
  "id": 24322039765,
  "attempt": 1,
  "name": "ci",
  "event": "push",
  "head_sha": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
  "conclusion": "success",
  "log_bytes": 3914200,
  "log_lines": 48213,
  "jobs": [{"name": "build", "conclusion": "success"}],
  "source": {"tool": "ci-archive", "integration": "after-ci-pipeline", "collected_at": "2026-09-23T14:20:03Z"}
}
```

With a bucket set, the entry also has `uri`, `bucket`, `key` and `size_bytes`.

### From your own CI

When the bucket must only be reachable from your runners, run the archive as a
GitHub Action instead. A workflow on `workflow_run: completed` fires once per
finished run attempt, re-runs included, after every log exists. The action
archives that attempt with the job's AWS credentials and records the same
`.ci.archive.runs[]` receipt on the commit the run built.

[examples/archive-ci-runs.yml](examples/archive-ci-runs.yml) is a complete
workflow. It uses OIDC both for your AWS role and for the Lunar Hub, so the
repository stores no keys. Things to know:

- The workflow file must be on the default branch, and `workflows:` names the
  workflows to archive.
- GitHub stops `workflow_run` chains after three levels, and the archiver is
  one of them. A workflow that already sits three `workflow_run` hops from a
  push or PR can't be archived this way.
- The job needs `actions: read`, plus `id-token: write` for OIDC. The role needs
  `s3:PutObject` on the prefix.
- Recording needs the `lunar` CLI on the runner, which `earthly/lunar-ci-tracer`
  installs. Set `record-in-lunar: "false"` to only upload.
- The runner needs curl 7.75+, jq and python3. GitHub-hosted runners have them.
- In a monorepo, receipts go on `<host>/<owner>/<repo>` unless `components`
  lists the component IDs to record on.

Inputs are documented in [action.yml](action.yml).

### Limits

- **GitHub only for now.** Run and log retrieval uses the GitHub Actions API;
  other providers need their own log-download path.
- **Size.** Log archives for a busy repository can be large; `max_archive_mb`
  bounds what gets uploaded per attempt.
