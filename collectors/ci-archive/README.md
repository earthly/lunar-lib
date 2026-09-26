# CI Archive Collector

Archives completed CI workflow runs and their logs to S3.

## Overview

Each time a CI workflow run finishes, re-runs included, this collector downloads
that run attempt's logs, bundles them with the run and its jobs, and uploads the
zip to S3. It appends a receipt to `.ci.archive.runs` saying where the archive
went, so consumers can find it without reconstructing the key. Useful when CI
logs need to outlive the provider's retention window: audit trails, incident
forensics, or compliance evidence.

It can also run in your own CI as a GitHub Action, so uploads use your runners'
credentials; see [From your own CI](#from-your-own-ci). Both write the same
receipts and objects.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ci.archive.runs[]` | array | One entry per archived run attempt: `uri`, `bucket`, `key`, `size_bytes`, run `id`, `attempt`, `name`, workflow `path`, `event`, `head_branch`, `head_sha`, `conclusion`, `started_at`, `completed_at`, `html_url`, `log_bytes`, `log_lines`, `jobs[]` (name, conclusion), `source`; for a run another workflow started, also `triggered_by_run_id` and `origin_source` |

Leave `s3_bucket` unset to record runs without archiving them: each entry has
the run, its jobs and its log's size and line count, but no `uri`, `bucket`,
`key` or `size_bytes`, and no AWS credentials are needed. It's a quick way to
check which runs fire and on which commits before wiring up a bucket.

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

## Collectors

| Collector | Description |
|--------|-------------|
| `backup-logs-s3` | Archives each finished run attempt to S3 and records it |

### When it runs

On the Hub's `after-ci-pipeline` hook: once per finished run attempt, for each
component the run's commit belongs to, after the attempt's logs exist. A re-run
is a new attempt and is archived again. Component checks don't wait for it.

It needs a Hub that has the `after-ci-pipeline` hook. In a monorepo, set
[`ciPipelines`](https://docs-lunar.earthly.dev/configuration/lunar-config/components#cipipelines)
on components to say which workflows are theirs.

A run another workflow started (`workflow_run`), such as a promote or smoke
test after a deploy, is archived under the commit its chain of runs started
from, where the Hub can follow the chain: the CI tracer reports each link, or the
workflow's `run-name` names the run that started it
([details](https://docs-lunar.earthly.dev/configuration/lunar-config/collector-hooks#runs-started-by-another-pipeline)).
Its receipt keeps GitHub's commit in `head_sha`, and `origin_source` says how the
chain was followed, or `unresolved` when it couldn't be and the run is filed at
GitHub's commit. Runs started by `schedule` or `workflow_dispatch` are filed at
the branch head when they started. To archive only runs a commit started, set
`include_events: push` (add `pull_request` for PR runs).

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

For a bucket in another account, set `aws_assume_role_arns` to a role there that
can write to it. The collector assumes that role with the credentials above,
sending `aws_external_id` if set, and uploads as the role. Its trust policy must
allow the snippet pod's role, and the pod's role needs `sts:AssumeRole` on it.
STS sessions are named `lunar-ci-archive-<run-id>-<attempt>`, so the bucket
account's CloudTrail shows which run each upload came from.

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
