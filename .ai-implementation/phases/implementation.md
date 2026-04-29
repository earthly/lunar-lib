# Phase: Implementation (and Testing)

You are in the **implementation** phase of a lunar-lib plugin PR. The
secondary reviewer approved the spec — your job now is to write code,
push it, run CI, **deploy to cronos, test, gather evidence, and post
that evidence on the PR**. All of that happens on the same PR you
opened in the spec phase.

```text
Spec → ... → Go-ahead → [Implement & test] → Evidence posted → Impl review → Merge
                            ▲ you are here
```

When test evidence is posted on the PR, switch to
[`phases/impl-review.md`](impl-review.md). Until then, you stay here.

For lifecycle context, conventions, and cross-cutting common mistakes,
see [`LUNAR-PLUGIN-PLAYBOOK-AI.md`](../LUNAR-PLUGIN-PLAYBOOK-AI.md).

---

## Implementation and testing are ONE unbroken unit

> Do not stop after writing code, pushing, and confirming `+lint` /
> `+test` / `+all` pass on GitHub. **CI green is not the finish line.**
> The work is not done until you have also:
>
> 1. Deployed the branch to cronos (Step 3 below),
> 2. Triggered collection against a real component (Step 5),
> 3. Gathered evidence (Step 7), and
> 4. Posted that evidence on the PR as a comment (Step 8).
>
> All of that happens under your own authority — it does NOT require
> reviewer approval, reviewer comments, or any human "go ahead." Keep
> going straight through.
>
> You are only "waiting for review" once the PR comment with test
> evidence is up. If you just wrote implementation code and pushed it,
> you are nowhere near waiting.

---

## What to produce

The actual scripts referenced in the YAML manifest:

- **Collectors:** Shell scripts (`.sh`) that use `lunar collect` to write data
- **Policies:** Python scripts (`.py`) that use `lunar_policy.Check` to assert

### Implementation rules

- **Alpine/BusyBox compatibility** — The `base-main` image uses Alpine. No GNU grep extensions (`-P`, `--include`). No gawk. Use `sed`, `find`, BusyBox-compatible patterns.
- **CI collectors should minimize dependencies** — CI collectors run `native` on the user's CI runner (GitHub Actions, GitLab CI, BuildKite, etc.). You should try to use only native tools like `bash`, `curl`, `git`, `grep`, `sed`, and `awk`. Avoid `jq`, `yq`, `python` unless necessary. Use `lunar collect` with key-value pairs instead of building JSON. Code collectors in `base-main` have `jq` and other tools — this restriction is CI-only.
- **Graceful degradation** — Missing secrets or configs should `exit 0` with a stderr message, not `exit 1`.
- **Copy helpers from similar plugins** — If the closest plugin has a `helpers.sh` with reusable logic, copy it rather than inventing new patterns.
- See [Common Mistakes](../LUNAR-PLUGIN-PLAYBOOK-AI.md#common-mistakes) in the overview before writing any code.

---

## Testing checklist

Follow this checklist **in order**. Every step must be completed before moving to the next.

**Start immediately after writing implementation code.** Don't wait for a reviewer to say "please test this" — cronos testing is your responsibility as the implementer, not something that gets triggered by review feedback. The moment you've pushed implementation code and watched `+lint` / `+test` / `+all` pass, go straight to Step 3 (deploy to cronos). You do not need approval to run these steps. If anything, **not** running these steps is the blocker that will make reviewers ask you to come back.

Reviewers expect to see your test evidence on the PR before their review is meaningful. A PR comment with Grafana screenshots + Component JSON output (Step 8) is what unblocks implementation review — not vice versa.

### Step 1: Write implementation code

Write the scripts referenced in the YAML manifest. Commit locally but do not push yet.

### Step 2: Docker image prerequisite (if custom Earthfile)

**Skip this step if the plugin uses the default `base-main` image (no Earthfile in the plugin directory).**

If the plugin has its own `Earthfile` (custom Docker image):

1. Ensure the plugin's Earthfile is wired into the root `Earthfile`'s `+all` target:
   ```
   BUILD --pass-args ./collectors/<name>+image
   ```
2. Push your branch to `earthly/lunar-lib` — CI builds and pushes images automatically.
3. Wait for lunar-lib CI to pass.
4. Verify the image exists on Docker Hub:
   ```bash
   docker manifest inspect earthly/lunar-lib:<plugin>-<normalized-branch>
   ```
   Branch `bender/eng-487-ruby` produces image tag `ruby-bender-eng-487-ruby` (slashes become dashes).
5. **Temporarily change `default_image`** in `lunar-collector.yml` to your branch image tag. The hub uses this field literally — it must point to an image that exists.

### Step 3: Deploy to cronos for testing

Add your plugin to the cronos test environment config.

1. Edit `pantalasa-cronos/lunar/lunar-config.yml` — add a branch reference:
   ```yaml
   - uses: github://earthly/lunar-lib/collectors/<name>@<branch>
   ```
2. Commit and push to `pantalasa-cronos/lunar`.
3. **Wait for the sync-manifest CI workflow to pass.** The hub only gets config updates when this workflow succeeds. Check with:
   ```bash
   gh run list --repo pantalasa-cronos/lunar --limit 3
   ```
   **Do NOT proceed until the sync build is green.**

### Step 4: Prepare a test component

You need component repos on `pantalasa-cronos` to test against. Either:

- **Modify an existing component** to exercise your scenarios (e.g. add a `go.mod`, Dockerfile, GitHub Actions workflow)
- **Create a new component repo** if none of the existing ones fit (e.g. a new programming language collector needs a repo in that language). If creating new: set up a GitHub Actions workflow with `runs_on: cronos`, add the component to `lunar-config.yml`, and verify the workflow runs successfully before testing collectors against it.

Examples of existing components on `pantalasa-cronos`:

| Component | Language/Type |
|-----------|--------------|
| `backend` | Go |
| `frontend` | Node.js |
| `auth` | Python |
| `kafka-go` | Go |
| `hadoop` | Java |
| `spark` | Java |

Check `pantalasa-cronos/lunar/lunar-config.yml` for the full list of registered components.

### Step 5: Trigger collection

Push a commit to the component repo you're testing against. This triggers CI, which triggers the hub to run collectors.

1. Push a commit to the component repo (e.g. `pantalasa-cronos/backend`).
2. Wait for the component repo CI to finish (~30 seconds).
3. Wait ~1 more minute for the hub to process collection results.

**For CI collectors** (hooks like `ci-after-job`, `ci-after-command`): local `lunar collector dev` is **not sufficient**. CI hooks only fire during actual CI runs. You must go through this full deploy+trigger cycle.

**For cron collectors** (hooks with `type: cron`): pushing a commit does NOT trigger collection. Cron collectors run on their configured schedule (e.g. `0 2 * * *` = daily at 2am UTC). To test on cronos:
- **Temporarily shorten the schedule** in the cronos config to `*/10 * * * *` (every 10 minutes). 10 min is the hub-enforced minimum — anything shorter gets silently bumped up to 10, so there's no point writing `*/5` or `*/1`.
- Wait for the cron to fire, then verify the run happened (see "Verifying cron collector runs" below).
- Revert the schedule to the real cadence once verified.
- Cron collectors with `clone-code: false` don't need the repo — they query external APIs directly, so no commit push is needed or useful.

**⚠️ Verifying cron collector runs — DO NOT use `components_latest` as the source of truth.**

`components_latest` reflects the **current** manifest, not the run history. The hub drops data from collectors that are no longer registered, so as soon as you remove a cron collector from the cronos manifest (e.g. during cleanup after testing), the `.your_category.*` JSON disappears from `components_latest` even though the collector ran successfully N times before. **An empty `components_latest` after cleanup is NOT evidence that cron didn't fire.** (Real mistake from ENG-495 testing: I committed a manifest cleanup 5 minutes after the 3rd successful pagerduty.oncall cron run, then queried `components_latest`, saw nothing, and incorrectly concluded "cron is broken" on the PR. Cron had fired three times perfectly.)

The truth source is the `hub` schema in the cronos PostgreSQL DB. Query it via the Grafana PostgreSQL datasource (discover the UID with `curl -s -b /tmp/cookies.txt https://cronos.demo.earthly.dev/api/datasources | jq '.[] | select(.type=="grafana-postgresql-datasource") | .uid'` — don't hardcode it, it differs per Grafana instance and can change when a datasource is recreated):
- **`hub.snippet_runs`** — every actual collector/policy invocation. `status='finished' AND exit_code=0` confirms the run succeeded. `started_at` tells you when it fired.
- **`hub.collection_records`** — what each collector actually wrote (`blob` = the JSONB merged into the component). `collection_source='cron'` confirms the run was cron-triggered, not a manual `lunar collector dev`.

```sql
-- "Did my cron collector ever fire, and when?"
SELECT s.name, COUNT(r.id) AS runs, MIN(r.started_at), MAX(r.started_at)
FROM hub.snippets s
LEFT JOIN hub.snippet_runs r ON r.snippet_id = s.id
WHERE s.name LIKE 'YOUR_COLLECTOR%'
GROUP BY s.name;

-- "What did it write, and was it cron-triggered?"
SELECT cr.created_at, cr.collection_source, cr.dimensions, cr.blob
FROM hub.collection_records cr
JOIN hub.snippets s ON s.id = cr.collector_id
WHERE s.name = 'YOUR_COLLECTOR' ORDER BY cr.created_at DESC LIMIT 10;
```

**Order of operations: verify the cron ran, THEN undeploy.** Do your cron verification (and any screenshots) BEFORE you push the manifest-cleanup commit that removes your collector from cronos. Once the collector is out of the manifest, `components_latest` is wiped and the only recourse is to go spelunking in the `hub.*` tables. Run the verification first, screenshot the evidence, THEN commit the cleanup.

**The Grafana UI screens to capture for cron-collector evidence:**

Both live on the same dashboard — `/d/den5tflglaolcd/runs-listing` — just with a different template-var filter each time. The var is `snippet_name` (not `name`).

1. **Collector runs** — `/d/den5tflglaolcd/runs-listing?var-snippet_name=YOUR_COLLECTOR`
   - Confirms the cron collector itself fired. Expect: one row per (component, run), `Runs ≥ 1`, `Errors = 0`, a recent `Latest` timestamp, and a reasonable `Avg Duration`. If you shortened the schedule for testing, you should see N rows matching the N fires you expected (remember the 10-min minimum interval).
   - Screenshot this with the filter visible at the top (proves it's your collector, not a whole-hub view).

2. **Policy runs** — `/d/den5tflglaolcd/runs-listing?var-snippet_name=YOUR_POLICY` (one URL per check if you have multiple — e.g. `oncall.schedule-configured`, `oncall.escalation-defined`, `oncall.min-participants`)
   - Confirms each policy check ran against every matching component. Expect: one row per component the policy applied to, `Errors = 0`. A row where `Errors > 0` means the policy crashed on that component — fix it, don't post evidence with errors.
   - Screenshot at least one check; if there are multiple and they exercise different code paths, screenshot each.

For a single-component deep dive (did the right JSON land?), the **Collector Details** dashboard at `/d/aepjhg9he4wlcc/collector-details?var-snippet_name=YOUR_COLLECTOR` shows the `collection_records` blobs the collector wrote — expand one to verify the JSON payload matches what you expect.

**Login note**: Grafana on cronos uses form auth (POST to `/login`), NOT HTTP Basic — Playwright's `httpCredentials` won't work. Fill `input[name="user"]` and `input[name="password"]` and submit. Credentials are in `~/.bender/grafana-credentials`.

### Step 6: Run local dev tests

All `lunar` commands must be run from the `pantalasa-cronos/lunar` directory with `LUNAR_HUB_TOKEN` set:

```bash
cd ~/repos/pantalasa-cronos-lunar  # or wherever the cronos lunar repo is cloned
export LUNAR_HUB_TOKEN=<token>     # should already be in your environment
```

**Test collectors:**
```bash
lunar collector dev <plugin>.<sub-collector> \
  --component <component> \
  --verbose
```

**Get component JSON (ground truth for correctness):**
```bash
lunar component get-json <component> > /tmp/component.json
```

**Test policies against real data:**
```bash
lunar policy dev <plugin>.<check> --component-json /tmp/component.json
```

**Test the full pipeline (collector output → policy):**
```bash
lunar collector dev <plugin>.<sub> --component <component> 2>&1 | \
  grep '^{' | jq -s 'reduce .[] as $item ({}; . * $item)' > /tmp/collected.json
lunar policy dev <plugin>.<check> --component-json /tmp/collected.json
```

**Minimum coverage:**

Collectors:
- [ ] **Data present** — Component that HAS the data. Verify correct, non-empty Component JSON with expected paths and values.
- [ ] **No data** — Component that does NOT have the data. Collector writes nothing (no empty arrays, no placeholders).
- [ ] **Missing config** — Missing secrets or optional inputs. Collector exits 0 with stderr message.

Policies:
- [ ] **Pass** — Component where all conditions are met. Check PASSes.
- [ ] **Fail** — Component where conditions are NOT met. Check FAILs (not error, not skip).
- [ ] **Skip** — Category doesn't apply (e.g. Go policy on Python repo). Check SKIPs gracefully.
- [ ] **Edge cases** — Missing fields, unexpected values, empty data. No crash.

### Step 7: Gather evidence

All of these are **required** and must be attached to the PR:

1. **Component JSON output** from `lunar component get-json` — paste the relevant section (the paths your collector writes to). This is the ground truth for correctness.

2. **Two screenshots from the cronos dashboard** (`cronos.demo.earthly.dev`):
   - **Component checks view** — scrolled to show the specific rows for your plugin's policy checks (e.g. `iac-scan.*`, `ruby.*`). Do NOT capture the top of the table — scroll to YOUR checks.
   - **Component JSON view** — tree expanded and scrolled to show the JSON section your collector writes (e.g. `.iac_scan`, `.lang.ruby`). Do NOT capture the top of the JSON tree — expand and scroll to YOUR data.

   Screenshots captured at the default scroll position (top of the page) are not valid evidence. Every screenshot must be scrolled to the relevant data. See Step 8.5 for detailed Playwright guidance on using `scrollIntoView()`. The actual JSON from the CLI is the ground truth — the screenshots prove the UI renders it correctly.

### Step 8: Post test results on the PR

0. **⚠️ PREREQUISITE: Ensure your plugin's Docker image exists on Docker Hub** — If your plugin has its own `Earthfile` (i.e. it builds a custom Docker image like `earthly/lunar-lib:<plugin>-<version>`), the image **must** be pushed to Docker Hub before cronos can use it. lunar-lib CI does this automatically on every push — but for new plugins, your first CI run on the branch must complete successfully before testing on cronos. Verify with:
   ```bash
   # Branch slashes are normalized to dashes in image tags
   docker manifest inspect earthly/lunar-lib:<plugin>-<normalized-branch>
   # Example: bender/eng-487-ruby → earthly/lunar-lib:ruby-bender-eng-487-ruby
   ```
   If the image doesn't exist, push a commit to your lunar-lib branch and wait for CI to build and push it. **Do NOT proceed to step 1 until the image exists** — the cronos sync will succeed but the collector will silently fail to run because the runner can't pull the image. Plugins without an Earthfile run on the base image and can skip this step.

1. **Add collector + policy to cronos config** — Edit `pantalasa-cronos/lunar`'s `lunar-config.yml` to reference your branch:
   ```yaml
   collectors:
     - uses: github://earthly/lunar-lib/collectors/YOUR_COLLECTOR@YOUR_BRANCH
       on: ["domain:engineering"]
   policies:
     - uses: github://earthly/lunar-lib/policies/YOUR_POLICY@YOUR_BRANCH
       enforcement: report-pr
   ```
   Push to `pantalasa-cronos/lunar` — the CI sync action deploys it to the cronos hub.

   ⚠️ **WAIT FOR THE BUILD TO PASS before making any commits to component repos.** The lunar config sync workflow must succeed first — if it fails, the hub won't know about your collector/policy and testing is pointless. Monitor with:
   ```bash
   GH_TOKEN=$(bender-gh-token pantalasa-cronos) gh run list --repo pantalasa-cronos/lunar --limit 1 --json status,conclusion
   ```
   Only proceed to step 2 once the build is green.

2. **Ensure the component repo has a GitHub Actions workflow running on `cronos`** — CI collectors only receive data from jobs that run on the `cronos` self-hosted runner. If you created a new component repo, it won't have a workflow yet — you must add one. If using an existing repo, verify its workflow uses `runs-on: cronos`.

   For language collectors, the workflow should exercise the language's toolchain so CI hooks fire:
   ```yaml
   # Example: .github/workflows/ci.yml for a Ruby component
   name: CI
   on:
     push:
       branches: ["**"]
     pull_request:
       branches: ["**"]
   jobs:
     build:
       runs-on: cronos
       steps:
         - uses: actions/checkout@v4
         - name: Install dependencies
           run: bundle install
         - name: Run tests
           run: rake spec
     audit:
       runs-on: cronos
       steps:
         - uses: actions/checkout@v4
         - name: Install dependencies
           run: bundle install
         - name: Run bundle audit
           run: |
             gem install bundler-audit
             bundle audit check --update
   ```

   For tool collectors (SBOM, SAST, etc.), add a job that runs your tool:
   ```yaml
   # Example: adding gitleaks to an existing workflow
   gitleaks:
     runs-on: cronos
     steps:
       - uses: actions/checkout@v4
       - name: Install & Run
         run: |
           curl -sSfL <tool-download-url> | tar xz -C /usr/local/bin
           <tool> scan --report-path report.json
   ```

   Push to trigger the CI workflow. The lunar agent on the `cronos` runner traces commands and feeds data to collectors. **Without this workflow, code collectors will still run (they clone the repo directly), but CI collectors will never fire.**

3. **Wait for CI + collection + UI settling** — Watch the workflow complete:
   ```bash
   GH_TOKEN=$(bender-gh-token pantalasa-cronos) gh run watch <run-id> --repo pantalasa-cronos/<component>
   ```
   Collection happens automatically after CI completes. Data appears in the cronos hub DB within ~1 minute.

   ⚠️ **After the workflow finishes, wait at least 1 minute before checking the UI.** The system needs time to settle pending states — if you check immediately, you may see stale/pending data that hasn't been fully processed yet. `sleep 60` is your friend here.

4. **Verify collected data** — Query the cronos DB via Grafana API:
   ```bash
   # Login
   curl -s -c /tmp/cookies.txt "https://cronos.demo.earthly.dev/login" \
     -X POST -H "Content-Type: application/json" \
     -d '{"user":"admin","password":"<password>"}'

   # Discover the PostgreSQL datasource UID (don't hardcode — it differs per instance)
   DS_UID=$(curl -s -b /tmp/cookies.txt "https://cronos.demo.earthly.dev/api/datasources" \
     | jq -r '.[] | select(.type=="grafana-postgresql-datasource") | .uid' | head -1)

   # Query component JSON for your category
   curl -s -b /tmp/cookies.txt "https://cronos.demo.earthly.dev/api/ds/query" \
     -X POST -H "Content-Type: application/json" \
     -d "{\"queries\":[{\"refId\":\"A\",\"datasource\":{\"uid\":\"$DS_UID\",\"type\":\"grafana-postgresql-datasource\"},
       \"rawSql\":\"SELECT component_json->'<category>' FROM components WHERE component_id = 'github.com/pantalasa-cronos/<component>' AND git_sha = '<sha>'\",
       \"format\":\"table\"}],\"from\":\"now-1h\",\"to\":\"now\"}"
   ```
   The `components_latest` materialized view may lag — query the `components` table directly with the specific `git_sha` for immediate results. **For cron collectors specifically, `components_latest` is also wiped when you remove the collector from the manifest** — see "Verifying cron collector runs" in Step 5 for the right way to check run history (`hub.snippet_runs` + `hub.collection_records`).

5. **Validate in the UI and capture evidence** — Check the cronos Grafana dashboards to confirm the collector and policy are working. This is a smoke test — you need to prove things are actually showing up in the UI, not just take random screenshots.

   **What to check and what counts as valid:**

   **A. Checks table (Component Details page)**
   - Navigate to the component details page and scroll to the checks table
   - Find the rows for your plugin's policy checks (e.g. `ruby.gemfile-exists`, `ruby.lockfile-exists`)
   - **Valid**: Checks show a green (pass) or red (fail) result — this means the policy ran and produced a verdict
   - **Invalid — pending (yellow)**: If the checks are still in a pending/yellow state, they haven't completed yet. This is NOT valid evidence. Wait and re-check.
   - **Invalid — stale (asterisk)**: If any check has an asterisk `*` next to it, the data is stale (from a previous run, not the current one). This is NOT valid evidence. Wait and re-check.
   - If checks remain pending or stale after ~10 minutes of waiting, there may be a problem with your policy or the cronos environment itself. Double-check your policy logic first. If the policy looks correct, escalate — the staging environment breaks sometimes and that's not your fault, but don't assume it's working when it isn't.

   **B. Component JSON page**
   - Navigate to the Component JSON page for your component
   - Expand the tree to show your collector's data section (e.g. `.lang.ruby`)
   - **Valid**: The JSON tree shows the fields your collector writes, especially anything populated by CI hooks (e.g. `.lang.ruby.cicd`, `.lang.ruby.bundler.cicd`)
   - **Invalid — missing section**: If the JSON section for your collector is completely missing, not all collectors have run yet. Check if CI completed, check if the code hook image exists on Docker Hub, and wait for the next collection cycle.
   - For CI-only data: if the component doesn't have a GitHub Actions workflow running on the cronos runner, CI hook collectors will never fire. Make sure the workflow exists and has completed at least once.

   **C. Errors**
   - Check the top of the component page for a "Some errors occurred" banner
   - If present, click through and check if any errors are from YOUR collector or policy
   - If they are — that's a bug. Fix it, push, and re-test. Do NOT post evidence with errors from your own plugin.

   **D. Cross-check external signals**
   - If checks are still pending or stale, look for corroborating evidence of environment problems beyond the Grafana UI:
     - **Hanging GitHub Actions runs**: Check whether the component repo's CI runs on `cronos` have completed. A GitHub check that's still "in progress" or "queued" long after the workflow should have finished (e.g. >5 minutes for a simple build) indicates the cronos runner is stuck or the hub isn't processing. Check the run directly: `gh run view <run-id> --repo <owner>/<repo>`.
     - **Policy sync failures**: Check if the cronos config repo's "Policy sync" workflow passed after your config change. If it failed, the hub doesn't know about your collector/policy.
   - These external signals help you distinguish "my code is broken" from "the environment is broken" — pending checks + a hanging CI run = environment issue, not a policy bug.

   **E. What to do if the UI is broken**
   - Empty tables, missing data, broken dashboards, or timeouts do NOT count as valid evidence
   - Don't assume "done" if something looks wrong — investigate first
   - If you've verified your collector/policy code is correct and the environment appears broken, speak up and let the reviewer know. The cronos staging environment has issues sometimes. That's fine, but you need to flag it rather than pretending everything is working.

   **Screenshots to capture (once validation passes):**
   - **Component details page** — checks table **scrolled so YOUR plugin's checks are visible in the viewport** with green/red results (no yellow pending, no stale asterisks). The default page load shows the top of the table — you MUST scroll down to the rows for your specific policy checks before capturing.
   - **Component JSON page** — tree expanded and **scrolled so your collector's data section is visible in the viewport** (e.g. `.iac_scan`, `.lang.ruby`). The default page load shows the top of the JSON tree — you MUST expand the relevant nodes and scroll to them before capturing.
   - **Collectors listing** (optional) — your collector shows runs > 0

   **How to capture screenshots:**

   Use Playwright to capture Grafana dashboards:
   1. Read Grafana credentials from `~/.bender/grafana-credentials`
   2. Navigate to `https://cronos.demo.earthly.dev/login` and log in
   3. Navigate to each dashboard URL (query `/api/search?type=dash-db` for dashboard UIDs — they differ between environments)
   4. **Wait for tables and panels to fully load before taking any screenshot.** Grafana dashboards load data asynchronously — tables may appear empty or show a loading spinner for several seconds after the page itself has loaded. After `waitForLoadState('networkidle')`, add an additional wait (5-8 seconds) and verify that the table/panel you need is actually populated before capturing. A screenshot of an empty or loading table is not valid evidence.
   5. **For JSON page**: expand the tree nodes for your collector's data section, then use `element.scrollIntoView()` to bring that section into the viewport before capturing. The screenshot must show the JSON paths your collector writes (e.g. `.iac_scan.findings`, `.lang.ruby.gems`), NOT the top of the tree.
   6. **For component details**: locate the rows in the checks table that correspond to your policy checks (e.g. search or scroll for `iac-scan.*`, `ruby.*`), then use `element.scrollIntoView()` to bring those rows into the viewport before capturing. The screenshot must show your specific check results, NOT the top of the table.
   7. **General rule**: A screenshot captured at the default scroll position (top of the page) is NOT valid evidence. Every screenshot must be scrolled to show the specific data your plugin produced. If the reviewer has to guess where your data is, the screenshot is useless.

   Upload screenshots to the PR comment as image attachments — they serve as proof that the plugin works end-to-end.

6. **Clean up** — Remove test files from the component repo after verifying results.

**Cross-org auth for pantalasa-cronos:**
```bash
GH_TOKEN=$(bender-gh-token pantalasa-cronos) gh <command> --repo pantalasa-cronos/<repo>
# Or for git operations:
git remote set-url origin "https://x-access-token:$(bender-gh-token pantalasa-cronos)@github.com/pantalasa-cronos/<repo>.git"
```

### Post test results on the PR

After testing and validating in the UI (see step 5 above), post a PR comment with evidence. The comment should be a quick smoke test summary showing things are working — not a novel.

```markdown
## Integration Test Evidence

### Checks table (Component Details)
- [screenshot of checks table showing your plugin's checks with pass/fail results]
- All checks resolved (no pending/yellow, no stale asterisks)

### Component JSON
- [screenshot of Component JSON tree showing your collector's data]
- CI-populated fields visible (e.g. `.lang.<language>.cicd`, `.lang.<language>.<tool>.cicd`)

### Errors
- No collector/policy errors on the component page (or: errors found and fixed — see commit <sha>)

### Notes
- <any caveats, e.g. "code hook collectors pending until Docker image is on main">
```

**What makes evidence valid vs. invalid:**
- Valid: checks show green/red results, JSON tree has your data, no errors from your plugin
- Invalid: pending checks (yellow), stale checks (asterisk), missing JSON sections, empty tables, tables still loading/rendering, error banners from your collector/policy, broken UI. If a table appears empty, confirm it has finished loading — Grafana panels render asynchronously and may still be fetching data.
- If the environment is broken and you can't get valid evidence, say so explicitly — don't post screenshots of broken state and call it done

### A note on unit tests

Unit tests are not required and should **not** be committed. The primary way to validate collectors and policies is `lunar collector dev` / `lunar policy dev` locally and testing on cronos. If you find unit tests helpful for debugging complex logic during development, that's fine — just don't include them in the PR.

---

## Cronos testing checklist (quick reference)

Use this as a sequential checklist during the testing phase:

```
1. [ ] Earthfile wired into +all (if custom image)
2. [ ] lunar-lib CI green, Docker image verified on Docker Hub
3. [ ] default_image temporarily changed to branch tag (if custom image)
4. [ ] Branch ref added to pantalasa-cronos/lunar/lunar-config.yml
5. [ ] Sync-manifest CI green
6. [ ] Test component prepared (existing modified or new created)
7. [ ] Commit pushed to component repo to trigger collection
8. [ ] Wait for component CI + 1 minute for hub processing
9. [ ] lunar component get-json output captured
10. [ ] 2 screenshots taken (checks view, JSON view)
11. [ ] Test results posted on PR (JSON + screenshots + test matrix)
12. [ ] Branch ref removed/reverted from cronos config
13. [ ] Sync-manifest CI green (post-cleanup)
14. [ ] default_image reverted to -main (if custom image)
```

Steps 12–14 are technically pre-merge prep — they're listed here so the
full testing-to-merge tail is in one place. They reappear in
[`phases/merge.md`](merge.md) for completeness.

---

## What's next

| Trigger | Read next |
|---|---|
| Test evidence posted on the PR | [`phases/impl-review.md`](impl-review.md) — wait for both reviewers to approve |
| Reviewer asks for spec changes mid-implementation | Re-read [`phases/spec.md`](spec.md) for the spec rules, make the changes, then re-test (back to Step 6 above) |
