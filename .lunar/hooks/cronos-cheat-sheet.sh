#!/bin/bash
# cronos-cheat-sheet.sh — agent-session-start hook.
# Stdin: SessionStart JSON (ignored). Stdout: cronos testing reference
# that Claude sees as additionalContext at session start.
#
# Purpose: surface the non-obvious bits of the cronos testing flow —
# hub DB schema, Grafana dashboard UIDs, common gotchas — so agents
# don't re-derive them from scratch on every PR. Distilled from
# BENDER-JOURNAL.md entries and the playbook.

cat <<'EOF'
## Cronos testing cheat-sheet

Quick reference for the "did my collector/policy run, and what did it
write?" queries you'll reach for during implementation testing. Full
detail is in `.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md` §§
"Testing" and "Integration Test Evidence" — this table is the stuff
you otherwise have to spelunk the hub schema for.

### Hub database tables (cronos PostgreSQL)

Query via Grafana datasource proxy. Discover the datasource UID at
runtime with `curl -s -b /tmp/cookies.txt
https://cronos.demo.earthly.dev/api/datasources | jq '.[] |
select(.type=="grafana-postgresql-datasource") | .uid'` — do NOT
hardcode; it rotates when datasources are recreated.

| Table | What's in it | Key columns |
|---|---|---|
| `hub.snippets` | One row per registered collector/policy, per manifest version | `id` (UUID), `name`, `code_path` (which script ran), `manifest_id` |
| `hub.snippet_runs` | Every actual collector/policy invocation | `id` (UUID), `snippet_id` (UUID → `snippets.id`), `component_name` (text, e.g. `github.com/pantalasa-cronos/backend`), `status` (`finished`/`error`/`queued`), `exit_code`, `started_at`, `finished_at`, `dim_pr`, `dim_head_sha` |
| `hub.collection_records` | What each collector actually wrote | `snippet_run_id` (UUID → `snippet_runs.id`), `component_id` (UUID → `components.id`), `blob` (JSONB), `collection_source` (`cron`/`code`/`ci`), `created_at` |
| `hub.policy_runs` | Every policy-check invocation (one row per check per component per run) | `id` (UUID), `component_id` (UUID → `components.id`), `policy_check_id` (UUID → `policy_checks.id`), `snippet_run_id`, `workflows_finished`, `created_at` — **no** `status` / `run_data` column here (see `run_data` / `policy_run_rollups` below) |
| `hub.run_data` | Assertion results keyed by policy run | `policy_run_id` (UUID → `policy_runs.id`), `status` (`pass`/`fail`/`error`/`skipped`), `failure_messages` (text[]), `metadata` (json) |
| `hub.policy_assertions` | Individual assertion op/result rows | `policy_run_id`, `op`, `args` (text[]), `result`, `failure_message` |
| `hub.policy_checks` | Check-definition registry | `id` (UUID), `name` (e.g. `readme-min-line-count`), `policy_id`, `paths` (text[]) |
| `hub.policy_run_rollups` | Pre-joined policy view (use this over manual joins when you can) | `policy_run_id`, `check_id`, `status`, `failure_messages`, `metadata`, `pr_number`, `repository_id`, `committed_at`, `run_created_at` |
| `hub.merged_collection_blobs` | Per-component merged JSON (what `lunar component get-json` returns) | `component_id` (UUID → `components.id`), `head_sha`, `merged_blob`, `last_record_at` |
| `hub.components` | Component registry | `id` (UUID), `name` (e.g. `github.com/pantalasa-cronos/backend`), `manifest_id` |
| `grafana.checks` / `public.checks` (views) | UI-surfaced per-check state | `component_id` (**text NAME**, not UUID — e.g. `github.com/pantalasa-cronos/backend`), `name`, `git_sha`, `status`, `policy_name`, `staleness` |

**The NAME-vs-UUID split**: `grafana.checks.component_id` and
`hub.snippet_runs.component_name` are both **text NAME strings** in
the full `github.com/<org>/<repo>` format. Every `component_id` column
inside `hub.*` (`collection_records`, `policy_runs`,
`merged_collection_blobs`, `policy_queue`, etc.) is a **UUID** that
joins to `hub.components.id`. So when you filter `grafana.checks` you
pass the name string; when you join `hub.policy_runs` you go through
`hub.components` to translate. Use this table as your source of truth;
if a column isn't covered above, fall back to
`information_schema.columns` once rather than guessing.

### Canonical queries

```sql
-- "Did my collector ever fire, and when?"
SELECT s.name, COUNT(r.id) AS runs,
       MIN(r.started_at) AS first_run,
       MAX(r.started_at) AS last_run
FROM hub.snippets s
LEFT JOIN hub.snippet_runs r ON r.snippet_id = s.id
WHERE s.name LIKE 'YOUR_COLLECTOR%'
GROUP BY s.name
ORDER BY last_run DESC NULLS LAST;

-- "What did my collector write for this component, and how?"
SELECT cr.created_at, cr.collection_source, cr.dimensions, cr.blob
FROM hub.collection_records cr
JOIN hub.snippet_runs sr ON sr.id = cr.snippet_run_id
JOIN hub.snippets s      ON s.id  = sr.snippet_id
JOIN hub.components c    ON c.id  = cr.component_id
WHERE s.name = 'YOUR_COLLECTOR'
  AND c.name = 'github.com/pantalasa-cronos/YOUR_COMPONENT'
ORDER BY cr.created_at DESC LIMIT 10;

-- "Did my policy fire on this component, and what assertions fired?"
-- Prefer policy_run_rollups (pre-joined, fast) for the pass/fail + messages.
SELECT prr.status,
       prr.failure_messages,
       pc.name AS check_name,
       prr.pr_number,
       prr.run_created_at
FROM hub.policy_run_rollups prr
JOIN hub.policy_checks pc ON pc.id = prr.check_id
JOIN hub.policy_runs pr   ON pr.id = prr.policy_run_id
JOIN hub.components c     ON c.id  = pr.component_id
WHERE pc.name LIKE 'YOUR_POLICY%'
  AND c.name = 'github.com/pantalasa-cronos/YOUR_COMPONENT'
ORDER BY prr.run_created_at DESC LIMIT 10;

-- Need the individual assertion rows (op/args/result), not just the rollup?
SELECT pa.op, pa.args, pa.result, pa.failure_message
FROM hub.policy_assertions pa
JOIN hub.policy_runs pr   ON pr.id = pa.policy_run_id
JOIN hub.policy_checks pc ON pc.id = pr.policy_check_id
JOIN hub.components c     ON c.id  = pr.component_id
WHERE pc.name = 'YOUR_CHECK_NAME'
  AND c.name  = 'github.com/pantalasa-cronos/YOUR_COMPONENT'
ORDER BY pa.created_at DESC LIMIT 20;

-- "What's in the latest merged blob for this component?"
SELECT mcb.head_sha, mcb.last_record_at,
       mcb.merged_blob -> 'your_category' AS category_data
FROM hub.merged_collection_blobs mcb
JOIN hub.components c ON c.id = mcb.component_id
WHERE c.name = 'github.com/pantalasa-cronos/YOUR_COMPONENT'
ORDER BY mcb.last_record_at DESC LIMIT 1;

-- Quick-filter snippet_runs by component (no JOIN needed: component_name is the filter column):
SELECT status, exit_code, started_at, finished_at, dim_pr, dim_head_sha
FROM hub.snippet_runs
WHERE component_name = 'github.com/pantalasa-cronos/YOUR_COMPONENT'
  AND started_at > now() - interval '1 hour'
ORDER BY started_at DESC;
```

### Grafana dashboard URLs + variables

Base: `https://cronos.demo.earthly.dev`

| Dashboard | UID | Key variables |
|---|---|---|
| Runs listing (collector + policy runs) | `/d/den5tflglaolcd/runs-listing` | `var-snippet_name=YOUR_NAME` |
| Collector details (raw blobs) | `/d/aepjhg9he4wlcc/collector-details` | `var-snippet_name=YOUR_COLLECTOR` |
| Component details (checks panel) | `/d/aecnnrn714em8d/component-details` | `var-component=<NAME>` (e.g. `github.com/pantalasa-cronos/backend`), optional `var-draft=false`, `var-git_sha=<sha>` |
| Component JSON (merged blob tree) | `/d/lujsqdc/component-json` | `var-component=<NAME>` (same shape) |

**Component variable gotcha**: `var-component` is the NAME string, NOT
the hub UUID and NOT `var-component_id`. URL-encode the full path
(e.g. `github.com%2Fpantalasa-cronos%2Fbackend`).

**Kiosk mode for screenshots**: append `&kiosk` to any URL.

**Grafana login**: form auth via POST to `/login` with
`input[name="user"]` + `input[name="password"]`. Playwright
`httpCredentials` / HTTP Basic won't work. Credentials in
`~/.bender/grafana-credentials`.

### Timing

A pantalasa-cronos/backend test round-trip is **~5–10 minutes
end-to-end**:

1. Component push → GitHub Actions (~2 min)
2. Cronos collector schedule pickup (~1–3 min delay)
3. `hub.policy_runs` insert (immediate after collection)
4. `grafana.checks` view refresh (~30 s after insert)

Don't add "fresh" commits to retrigger — the next scheduled sweep
picks up the existing HEAD. Use `Monitor` to poll
`hub.snippet_runs.started_at > <ref-timestamp>` instead of spinning
new commits.

### Known traps

- `public.components_latest` (a view; NOT `hub.components_latest`) gets
  wiped when you remove a collector from the manifest. Don't use it
  for run history; use `hub.snippet_runs` + `hub.collection_records`
  directly.
- A new manifest sync registers a NEW `hub.snippets` row with a
  different `snippet_id` for the same plugin name. Runs queued before
  the sync land against the OLD id. Join on `snippets.name` (not a
  cached snippet_id) when verifying "the latest manifest fired at
  least once".
- `grafana.checks` filters out `status = 'skipped'` AND restricts to
  the latest manifest. A correct skip OR a revert to `@main` before
  the new policy is in `@main` both make the row disappear from the
  UI — query `hub.policy_run_rollups` / `hub.run_data` directly if
  you need the full history.
- The checks-panel SQL in Grafana takes ~27s on cronos, right at the
  30s datasource timeout edge. "No data" in the UI can hide a working
  query; confirm via `/api/ds/query` before concluding the backend is
  broken.
- `hub.policy_runs` has no `status` or `run_data` column of its own —
  the outcome lives in `hub.run_data` (one-to-one by `policy_run_id`)
  or in the pre-joined `hub.policy_run_rollups`. If you reach for
  `pr.status` you'll get a "column does not exist" error.
EOF
