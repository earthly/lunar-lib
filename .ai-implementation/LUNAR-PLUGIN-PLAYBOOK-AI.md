# Lunar Plugin PR Playbook

Step-by-step playbook for AI agents creating lunar-lib collector and policy PRs end-to-end. This is a **bot-mode** workflow — the agent works autonomously through each phase, pausing only at explicit review gates.

---

## Overview

Every lunar-lib plugin PR follows this lifecycle on a **single PR**:

```text
Spec → Primary review & iterate → Secondary review → Implement & test → Review & iterate → Approval → Merge
```

| Stage | What you do | What you wait for |
|-------|------------|-------------------|
| **Spec** | Create YAML manifest, README, SVG icon. Push as draft PR. Assign the primary reviewer. | Primary reviewer comments. Address feedback. Iterate. |
| **Secondary review** | — | Primary reviewer assigns a secondary reviewer when satisfied. Wait for the secondary reviewer to approve. |
| **Go-ahead gate** | — | **The secondary reviewer approves the spec.** This is your signal — start implementing immediately. |
| **Implementation & testing** | Write code, deploy to cronos, test, gather evidence, post results, undeploy from cronos. Push to PR. | Reviewers comment. Address feedback. Spec changes may be requested even at this stage — make them and re-test. |
| **Approval gate** | — | **Both reviewers** approve the implementation via GitHub review. |
| **Merge** | Squash-merge. Re-add to cronos with `@main`. Clean up. | — |

**Never skip the spec stage.** The spec is cheap to iterate on. Code is expensive to throw away.

### How the review flow works

1. **Primary reviewer iterates on the spec.** This is the person who requested the work or was assigned first. They go back and forth with you — comments, change requests, discussion — until they're satisfied with the design.
2. **Primary reviewer assigns a secondary reviewer.** This signals the primary review is done. They wouldn't assign someone else unless they're happy.
3. **Secondary reviewer approves.** They may also request changes first — address them, then they approve.
4. **You start implementing immediately.** The secondary reviewer's approval is the trigger. **Do not ask permission. Do not re-propose a plan. Do not wait for further instructions.** Begin writing code and testing right away.

---

## Before You Start

### 1. Ensure latest main

From the lunar-lib repository root:

```bash
git checkout main && git pull origin main
```

### 2. Build and install the latest Lunar CLI

Clone the `earthly/lunar` repo locally (the remote earthly target syntax `earthly github.com/earthly/lunar+build-cli` requires GitHub auth in buildkit, which cloud agents typically don't have):

```bash
# Clone once (skip if already cloned)
git clone https://github.com/earthly/lunar.git /path/to/lunar

# Build from the local clone
cd /path/to/lunar && git pull origin main
earthly +build-cli
sudo cp dist/lunar-linux-amd64 /usr/local/bin/lunar
```

### 3. Read the docs

Read the Lunar docs at https://docs-lunar.earthly.dev — this covers core concepts, CLI usage, and plugin SDKs.

Then read these files in `ai-context/` (relative to lunar-lib root):

| File | Why |
|------|-----|
| `about-lunar.md` | What Lunar is |
| `core-concepts.md` | Architecture |
| `collector-reference.md` | How collectors work (if building a collector) |
| `policy-reference.md` | How policies work (if building a policy) |
| `component-json/conventions.md` | **Schema design rules — critical.** Read the "Presence Detection" and "Anti-Pattern: Boolean Fields" sections carefully. |
| `component-json/structure.md` | All existing Component JSON paths |

### 4. Study the closest existing plugin

Find the most similar existing collector or policy and read every file. Understand the pattern before writing anything. Examples:

| If building... | Study this |
|----------------|-----------|
| Issue tracker collector | `collectors/jira/` |
| Security scanner collector | `collectors/semgrep/` or `collectors/snyk/` |
| Language collector | `collectors/golang/` or `collectors/java/` |
| Repo/file check policy | `policies/repo/` |
| Security policy | `policies/sast/` or `policies/sca/` |

---

## Spec PR

### What to produce

Three files (no implementation code):

```text
collectors/<name>/
├── lunar-collector.yml    # Plugin manifest
├── README.md              # Documentation
└── assets/
    └── <name>.svg         # Icon (black fill!)
```

Or for policies:

```text
policies/<name>/
├── lunar-policy.yml       # Plugin manifest
├── README.md              # Documentation
├── requirements.txt       # lunar-policy==0.2.2 (if Python)
└── assets/
    └── <name>.svg         # Icon (black fill!)
```

### YAML manifest rules

- Copy the structure from the closest existing plugin.
- `mainBash`/`mainPython` fields should reference filenames that **don't exist yet** — that's fine for the spec PR.
- Include `inputs`, `secrets`, and `example_component_json`.
- **Validate Component JSON paths** against `component-json/conventions.md`. See [Common Mistakes](#common-mistakes) for what to watch out for.

### README rules

Follow the template in `collector-README-template.md` or `policy-README-template.md`. Include:

- One-line description
- Overview (2-3 sentences)
- Collected Data table (paths, types, descriptions)
- Sub-collector/check table
- Installation YAML example
- Inputs table
- Notes on anything non-obvious

### SVG icon rules

- **Must use `fill="black"`** — not white, not colored. The website converts to white automatically. Black is visible in GitHub PR diffs.
- Source from [simple-icons](https://github.com/simple-icons/simple-icons) when possible:
  ```bash
  curl -sL "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/<name>.svg"
  ```
- Strip `<title>` tags and `role="img"`. Add `fill="black"` to all `<path>` elements.
- Wrap in a clean `<svg xmlns="http://www.w3.org/2000/svg" viewBox="...">` container.

### Status: experimental vs beta

The `status` field in the YAML manifest depends on how thoroughly the plugin can be tested:

| Status | When to use |
|--------|-------------|
| `experimental` | Plugin requires a 3rd-party vendor, API, or account that you don't have access to. You can only test the logic without real integration. |
| `beta` | Plugin can be fully tested end-to-end — no missing vendor access or untestable integrations. |
| `stable` | Proven in production over time. You won't set this on a new plugin. |

**Call this out in the PR description at spec time.** If the plugin needs vendor access you don't have, explain what you can and can't test, and what secrets/accounts would be needed to fully validate it. Reviewers may decide to set up an account and provide secrets so it can be tested properly.

### PR description

The PR description must include:

1. **What's included** — list the files
2. **Design summary** — which Component JSON paths are written, why, and how they relate to existing paths
3. **Relationship to existing plugins** — does this reuse an existing policy? Does it write to the same normalized paths as another collector?
4. **Testing plan** — what components you'll test against, expected results per component, edge cases. **If vendor access is missing**, explain what can be tested without it and what would be needed for full integration testing.
5. **Open questions** — anything you're unsure about (architecture, naming, path choices)

### Open the PR

Create a draft PR with the spec files only. Assign the **primary reviewer** (the person who requested the work, or who will iterate on the design with you).

### Then wait for go-ahead

**Do not write implementation code until the secondary reviewer approves.**

The primary reviewer will iterate with you — comments, change requests, back and forth. Address their feedback and push updates.

When the primary reviewer is satisfied, they will assign a **secondary reviewer**. Wait for the secondary reviewer to approve the spec.

**While waiting:**
- Address review comments. Push updates.
- If reviewers are discussing with each other (e.g. @-mentioning each other), **wait for them to reach a conclusion** before acting.
- They may address you as "claude" or "devin" or "bender" in PR comments — treat that as a direct instruction.

**When the secondary reviewer approves: start implementing immediately.** Their approval is the "go ahead" signal. Do not ask for permission or confirmation — begin Step 1 of the implementation checklist below.

---

## Implementation (same PR)

### What to produce

The actual scripts referenced in the YAML manifest:

- **Collectors:** Shell scripts (`.sh`) that use `lunar collect` to write data
- **Policies:** Python scripts (`.py`) that use `lunar_policy.Check` to assert

### Implementation rules

- **Alpine/BusyBox compatibility** — The `base-main` image uses Alpine. No GNU grep extensions (`-P`, `--include`). No gawk. Use `sed`, `find`, BusyBox-compatible patterns.
- **CI collectors should minimize dependencies** — CI collectors run `native` on the user's CI runner (GitHub Actions, GitLab CI, BuildKite, etc.). You should try to use only native tools like `bash`, `curl`, `git`, `grep`, `sed`, and `awk`. Avoid `jq`, `yq`, `python` unless necessary. Use `lunar collect` with key-value pairs instead of building JSON. Code collectors in `base-main` have `jq` and other tools — this restriction is CI-only.
- **Graceful degradation** — Missing secrets or configs should `exit 0` with a stderr message, not `exit 1`.
- **Copy helpers from similar plugins** — If the closest plugin has a `helpers.sh` with reusable logic, copy it rather than inventing new patterns.
- See [Common Mistakes](#common-mistakes) before writing any code.

---

## Testing

Follow this checklist **in order**. Every step must be completed before moving to the next.

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
- **Temporarily shorten the schedule** in the cronos config (e.g. `*/5 * * * *` for every 5 minutes) to get faster feedback. **The hub enforces a minimum cron interval of 10 minutes** — anything shorter gets bumped, so don't expect a 5-minute schedule to actually fire every 5 minutes.
- Wait for the cron to fire, then verify the run happened (see "Verifying cron collector runs" below).
- Revert the schedule to the real cadence once verified.
- Cron collectors with `clone-code: false` don't need the repo — they query external APIs directly, so no commit push is needed or useful.

**⚠️ Verifying cron collector runs — DO NOT use `components_latest` as the source of truth.**

`components_latest` reflects the **current** manifest, not the run history. The hub drops data from collectors that are no longer registered, so as soon as you remove a cron collector from the cronos manifest (e.g. during cleanup after testing), the `.your_category.*` JSON disappears from `components_latest` even though the collector ran successfully N times before. **An empty `components_latest` after cleanup is NOT evidence that cron didn't fire.** (Real mistake from ENG-495 testing: I committed a manifest cleanup 5 minutes after the 3rd successful pagerduty.oncall cron run, then queried `components_latest`, saw nothing, and incorrectly concluded "cron is broken" on the PR. Cron had fired three times perfectly.)

The truth source is the `hub` schema in the cronos PostgreSQL DB (Grafana datasource UID `PCC52D03280B7034C`):
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

You can also use the Grafana **Runs** dashboard (`/d/den5tflglaolcd/runs-listing?var-snippet_name=YOUR_COLLECTOR`) — note the template var is `snippet_name`, not `name`. **If you must verify cron history, do it BEFORE you commit any manifest cleanup**, otherwise you'll need to query `hub.*` to recover the history.

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

   # Query component JSON for your category
   curl -s -b /tmp/cookies.txt "https://cronos.demo.earthly.dev/api/ds/query" \
     -X POST -H "Content-Type: application/json" \
     -d '{"queries":[{"refId":"A","datasource":{"uid":"PCC52D03280B7034C","type":"grafana-postgresql-datasource"},
       "rawSql":"SELECT component_json->'"'"'<category>'"'"' FROM components WHERE component_id = '"'"'github.com/pantalasa-cronos/<component>'"'"' AND git_sha = '"'"'<sha>'"'"'",
       "format":"table"}],"from":"now-1h","to":"now"}'
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

## Implementation review

Claude will automatically review the PR via the `claude-code-action` GitHub Action. Address its feedback, but **use judgment** — Claude sometimes flags things that aren't real issues. If a comment is wrong or irrelevant, reply explaining why and resolve the thread. When you've addressed a valid comment (pushed a fix), resolve that thread too. Don't leave conversations hanging.

**Implementation review may trigger spec changes.** Reviewers may ask you to adjust the YAML manifest, README, or Component JSON paths even after implementation is added. This is normal — make the changes. **Re-test after significant changes** (logic changes, new assertions, changed Component JSON paths). A quick `lunar collector dev` or `lunar policy dev` run is enough — post updated results on the PR if the previous results are now stale.

Wait for **both reviewers** to approve the PR via GitHub review.

**While waiting:**
- Fix CI failures automatically.
- Address review comments. Push fixes. Reply to reviewers on the PR.
- If reviewers are discussing with each other, wait for them to reach a conclusion before acting.
- **Do not merge** until you have both approvals.

---

## Merge

### Pre-merge checklist

- [ ] CI is green
- [ ] Claude review comments addressed
- [ ] **Both reviewers approved** the implementation
- [ ] Test results with JSON output + screenshots posted on PR
- [ ] No unresolved review threads
- [ ] Cronos config cleaned up (no branch refs remaining)
- [ ] `default_image` reverted to `-main` tag (if custom Earthfile)

### Squash-merge

Squash-merge the PR and delete the branch.

### Post-merge: contribute back to cronos

**For NEW plugins:** re-add the collector/policy to `pantalasa-cronos/lunar/lunar-config.yml`, now referencing `@main`:

```yaml
- uses: github://earthly/lunar-lib/collectors/<name>@main
```

Commit, push, and **verify the sync-manifest CI build passes**.

**For EXISTING plugins:** the config already points to `@main`, so nothing to do.

### Clean up

1. Delete the worktree/branch locally.
2. Write down what you learned — append to your learning journal.
3. Close the Linear ticket if still open.

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

---

## Common Mistakes

These are the most frequent mistakes AI agents make on lunar-lib PRs. Read this section before writing any code.

### Component JSON schema

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Adding boolean fields (e.g. `.ci.artifacts.sbom_generated = true`) | Object presence IS the signal. If `.sbom.cicd` exists, that means SBOM was generated. A separate boolean is redundant. | Only use explicit booleans when the same collector writes both `true` and `false`. |
| Putting normalized data under `.native` | `.native.<tool>` is for raw tool-specific output. Normalized, tool-agnostic data belongs at the category level (e.g. `.sca`, `.sast`). | Move normalized fields up to the category. Keep only raw output in `.native`. |
| Inventing new top-level categories | Data may fit an existing category. | Check `component-json/structure.md` for existing categories first. |
| Naming categories after tools | Categories describe WHAT, not HOW. | `.sca`, not `.snyk`. `.sast`, not `.semgrep`. |

### Policy code

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| `return c` after `c.skip()` | `c.skip()` raises `SkippedError` which exits the `with` block immediately. `return c` is dead code and will never execute. | Remove `return c` after `c.skip()`. |
| Using `c.exists()` for skip logic | `c.exists()` raises `NoDataError` if missing — your `c.skip()` after it is unreachable. | Use `c.get_node(path).exists()` which returns `True`/`False`. |
| Calling `get_value()` without checking `exists()` | Crashes with `ValueError` if the path doesn't exist. | Always call `node.exists()` before `node.get_value()`. |
| Skipping when a sibling check already fails | Inflates the compliance score. If the guardrail IS relevant but upstream data is missing because a sibling requirement isn't met, the component should be penalized. | Let it fail (don't skip). See `ai-context/policy-reference.md` for skip vs fail guidance. |

### Collector code

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Writing empty data when nothing is found | Pollutes Component JSON. Policies evaluate against empty arrays instead of skipping. | If there's nothing to collect, write nothing. Absence of a key = feature doesn't apply. |
| Using GNU grep extensions (`-P`, `--include`) | `base-main` image is Alpine/BusyBox. GNU extensions don't exist. | Use `sed`, `find`, BusyBox-compatible patterns. |
| Using `jq` in CI collectors | CI collectors run `native` on user CI runners. `jq` may not be installed. | Use `lunar collect` with multiple key-value pairs. See existing CI collectors for patterns. |
| Exiting with `exit 1` on missing config | Fails the collector run. Users see errors for optional features. | `exit 0` with a stderr message explaining what's missing. |
| Adding cleanup code (`trap`, `rm`, temp file management) | Code collectors run in disposable Docker containers. The filesystem is thrown away when the collector finishes. | Don't bother. Use fixed paths like `/tmp/output.json`. No `mktemp` needed either. |

### SVG icons

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Using `fill="white"` or colored fills | White is invisible on GitHub's white PR diff background. Reviewers can't see the icon. | Use `fill="black"`. The website converts to white automatically. |
| Solid background rectangles | Appears as a flat rectangle on the website's dark background. | Use transparent background (no `<rect>` filling the viewBox). |
| Leaving `<title>` tags and `role="img"` | Unnecessary metadata that bloats the SVG. | Strip them. |

### PR workflow

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Starting implementation before secondary reviewer approves | The spec may change significantly during review. Implementation effort is wasted. | Wait for the secondary reviewer's approval. |
| Using `git add .` or `git add -A` | Stages unintended files (test configs, temp files, etc.). | Always `git add` specific directories: `git add collectors/<name>/` or `git add policies/<name>/`. |
| Merging with only one approval | Both reviewers need to approve unless one explicitly waives. | Wait for both. |
| Not posting test results on the PR | Reviewers need evidence, not trust. | Always post test results with JSON output, screenshots, and the test matrix template. |
| Ignoring Claude review feedback | Claude auto-reviews open PRs. Unresolved comments slow down human review. | Address or reply to every Claude review comment before requesting human review. |
| Leaving branch refs in cronos config | The branch gets deleted on merge, breaking all manifest syncs. | Undeploy from cronos before pushing for review (Step 9). |

### Docker images

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Using `earthly/lunar-scripts:1.0.0` | Legacy image. | Use `earthly/lunar-lib:base-main` or `earthly/lunar-lib:<name>-main`. |
| Using `native` for code collectors | Code collectors must run in a container. | Use `earthly/lunar-lib:base-main` or a custom image. |
| Committing a temporary image tag | The tag won't exist after your test branch is cleaned up. | Always use `-main` tag in committed code. |

---

## Quick Reference: Conventions

### Component JSON paths

- **Categories describe WHAT, not HOW** — `.sca`, not `.snyk`
- **Object presence = signal** for conditional collectors (no redundant booleans)
- **Explicit booleans** only when the same collector writes both `true` and `false`
- **`.native.<tool>`** for raw tool output; normalized data at category level
- **`.source`** metadata: `{tool, version, integration}`

### PR titles

- `[Spec Only] Add <name> collector` — when the PR contains only the spec (YAML, README, icon)
- `[Implementation] Add <name> collector` — update the title once implementation is added
- No Linear ticket prefix needed for lunar-lib PRs (unlike lunar core)

---

## Improving This Document

If you encounter something unclear, make a mistake that wasn't covered here, or discover a workaround that a future agent would benefit from — **open a separate PR to update this document**. Don't just fix it in your head and move on. If you think a future agent would make the same mistake, add it to the [Common Mistakes](#common-mistakes) section or clarify the relevant instructions.

This is how the playbook stays useful over time.
