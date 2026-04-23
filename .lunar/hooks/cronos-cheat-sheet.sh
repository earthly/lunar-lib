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
| `hub.snippets` | One row per registered collector/policy, per manifest version | `id`, `name`, `code_path` (which script ran) |
| `hub.snippet_runs` | Every actual collector/policy invocation | `snippet_id`, `status` (`finished`/`error`/`queued`), `exit_code`, `started_at`, `finished_at`, `collection_source` (`cron`/`code`/`ci`) |
| `hub.collection_records` | What each collector actually wrote | `snippet_id`, `component_id` (UUID), `blob` (JSONB), `created_at`, `collection_source` |
| `hub.policy_runs` | Every policy-check invocation | `snippet_id`, `component_id`, `status`, `run_data` (assertions JSONB) |
| `hub.merged_collection_blobs` | Per-component merged JSON (what `lunar component get-json` returns) | `component_id` (UUID!), `head_sha`, `merged_blob`, `last_record_at` |
| `hub.components` | Component registry | `id` (UUID), `name` (e.g. `github.com/pantalasa-cronos/backend`) |
| `grafana.checks` (view) | UI-surfaced per-check state | `name`, `component_id` (NAME, not UUID), `git_sha`, `status`, `manifest_version`, `staleness` |

**Schema mismatch to watch for**: `snippet_runs` / `policy_runs` /
`grafana.checks` use the component NAME string as `component_id` —
but `merged_collection_blobs` / `hub.components.id` use the UUID.
Always check `information_schema.columns` before writing a join
instead of guessing.

### Canonical queries

```sql
-- "Did my collector ever fire, and when?"
SELECT s.name, COUNT(r.id) AS runs,
       MIN(r.started_at), MAX(r.started_at)
FROM hub.snippets s
LEFT JOIN hub.snippet_runs r ON r.snippet_id = s.id
WHERE s.name LIKE 'YOUR_COLLECTOR%'
GROUP BY s.name;

-- "What did it write, and was it cron-triggered?"
SELECT cr.created_at, cr.collection_source, cr.dimensions, cr.blob
FROM hub.collection_records cr
JOIN hub.snippets s ON s.id = cr.snippet_id
WHERE s.name = 'YOUR_COLLECTOR'
ORDER BY cr.created_at DESC LIMIT 10;

-- "Did my policy produce assertions for this component?"
SELECT pr.status, pr.run_data, pr.started_at
FROM hub.policy_runs pr
JOIN hub.snippets s ON s.id = pr.snippet_id
JOIN hub.components c ON c.id = pr.component_id
WHERE s.name LIKE 'YOUR_POLICY%'
  AND c.name = 'github.com/pantalasa-cronos/YOUR_COMPONENT'
ORDER BY pr.started_at DESC LIMIT 10;

-- "What's in the latest merged blob for this component?"
SELECT mcb.head_sha, mcb.last_record_at,
       mcb.merged_blob -> 'your_category' AS category_data
FROM hub.merged_collection_blobs mcb
JOIN hub.components c ON c.id = mcb.component_id
WHERE c.name = 'github.com/pantalasa-cronos/YOUR_COMPONENT'
ORDER BY mcb.last_record_at DESC LIMIT 1;
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

- `components_latest` gets wiped when you remove a collector from the
  manifest. Don't use it for run history; use `hub.snippet_runs` +
  `hub.collection_records` directly.
- A new manifest sync registers a NEW `snippets` row with a different
  `snippet_id`. Runs queued before the sync land against the OLD id.
  Filter `snippet_runs` by `snippet_id`, not by name, when verifying
  that a specific manifest version fired.
- `grafana.checks` filters `WHERE status <> 'skipped'` AND `WHERE
  s.manifest_id = latest(hub.manifests)`. A correct skip OR a revert
  to `@main` before the new policy is in `@main` both make the row
  disappear from the UI — go to `public.checks` directly.
- The checks-panel SQL takes ~27s on cronos at the 30s Grafana query
  timeout edge. "No data" in the UI can hide a working query; confirm
  via `/api/ds/query` before concluding the backend is broken.
EOF
