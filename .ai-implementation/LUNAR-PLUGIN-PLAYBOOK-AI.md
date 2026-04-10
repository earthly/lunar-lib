# Lunar Plugin PR Playbook

Step-by-step playbook for cloud-based AI agents (Devin, etc.) to create lunar-lib collector and policy PRs end-to-end. This is a **bot-mode** workflow — the agent works autonomously through each phase, pausing only at explicit review gates.

---

## Overview

Every lunar-lib plugin PR follows this lifecycle on a **single PR**:

```text
Spec → Requester reviews → Second reviewer reviews → Second reviewer approves (go-ahead) → Implement → Requester reviews → Approval → Merge
```

**Requester** = the human who asked for this work (Linear ticket assignee, Slack requester, or whoever prompted the AI agent directly).

| Stage | What you do | What you wait for |
|-------|------------|-------------------|
| **Spec** | Create YAML manifest, README, SVG icon. Push as PR (non-draft). Assign **only the requester** as reviewer. | Requester comments. Address feedback. Iterate. |
| **Requester → second reviewer handoff** | — | **Requester** assigns a second reviewer when they're satisfied with the spec. |
| **Second reviewer spec review** | Address the second reviewer's feedback. Iterate. | Second reviewer comments. |
| **Go-ahead gate** | — | **Second reviewer approves** the spec. This is the green light to implement. |
| **Implementation** | Add scripts to the same PR. Test. Post results. | **Requester** reviews implementation. Address feedback. Spec changes may still be requested — make them. |
| **Approval gate** | — | **Requester approves** the PR (or merges directly). |
| **Merge** | Squash-merge (or requester merges directly). Clean up worktree. | — |

**Never skip the spec stage.** The spec is cheap to iterate on. Code is expensive to throw away.

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

Create a PR with the spec files only (non-draft mode). Assign **only the requester** (the human who asked for this work) as reviewer. Do NOT assign a second reviewer yourself — the requester will assign one when the spec is ready.

### Then wait for go-ahead

**Do not write implementation code until the second reviewer approves the spec.**

⚠️ **THIS IS A HARD GATE.** Addressing review comments on the spec (updating YAML, README, fixing names, etc.) is NOT approval to implement. Even if you've addressed every comment, even if CI is green, even if the spec looks perfect — do NOT create `.sh` or `.py` implementation files until the second reviewer's GitHub review status is "APPROVED". Review comments ≠ go-ahead. Only an explicit approval counts.

The review flow is sequential:

1. **Requester reviews first.** Address their feedback. Iterate until they're satisfied. This means updating spec files only (YAML, README, SVG). No implementation code.
2. **Requester assigns a second reviewer.** When the requester is happy with the spec, they'll assign someone else to review. You do NOT assign the second reviewer yourself.
3. **Second reviewer reviews.** Address their feedback. Iterate. Still spec files only.
4. **Second reviewer approves = go-ahead.** Once the second reviewer's GitHub review status is "APPROVED", you can proceed to implementation.

**Automatic testing on approval:** When the second reviewer approves the spec, the full integration testing plan (cronos testing, screenshots, component JSON verification) should be executed automatically as part of the implementation phase — don't wait for a separate instruction. Spec approval IS the green light to implement AND test.

**Exception:** The requester may explicitly tell you to go ahead with implementation even without the second reviewer's approval (e.g. if that person is away). If the requester says to proceed, that's a valid go-ahead — follow their instruction.

**While waiting:**
- Address review comments. Push updates to spec files only.
- If reviewers are discussing with each other (e.g. @-mentioning each other), **wait for them to reach a conclusion** before acting.
- They may address you as "claude" or "devin" in PR comments — treat that as a direct instruction.

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
- **Custom Docker images must be wired into CI** — If your plugin needs an Earthfile (installs external tools, uses a non-base image), you must add it to the root Earthfile's `+all` target: `BUILD --pass-args ./<type>/<name>+image`. Without this, CI won't build or push the image and it won't exist on Docker Hub.
- See [Common Mistakes](#common-mistakes) before writing any code.

### Testing

Test before pushing. All `lunar` commands must be run from the `pantalasa-cronos/lunar` repo — clone it first if you haven't:

```bash
git clone https://github.com/pantalasa-cronos/lunar.git
```

Run all `lunar collector dev` and `lunar policy dev` commands from inside this repo. The `--config-dir` flag defaults to `.` so make sure you `cd` into the cronos lunar repo before running commands.

**`LUNAR_HUB_TOKEN` must be set.** The Lunar CLI requires this environment variable to communicate with the hub. It should already be provided in your environment as a secret — if it's not set, `lunar` commands will fail. Do not hardcode it anywhere.

#### 1. Test collectors

```bash
lunar collector dev <plugin>.<sub-collector> \
  --component <component> \
  --verbose \
  --secrets "SECRET_NAME=value"
```

Verify:
- Correct Component JSON paths are written
- Output structure matches `example_component_json`
- Missing secrets/configs cause `exit 0` with a stderr message, not `exit 1`

#### 2. Test policies

```bash
# Get live component JSON from hub
lunar component get-json <component> > /tmp/component.json

# Run policy against it
lunar policy dev <plugin>.<check> --component-json /tmp/component.json
```

Test each check against:
- A component where data exists → expect PASS
- A component where data is missing → expect SKIP (not ERROR)
- Edge cases (missing fields, unexpected values) → expect graceful handling

#### 3. Test the collector → policy pipeline

Chain them: run the collector, capture its output, feed to the policy:

```bash
# Capture collector output and merge JSON lines
lunar collector dev <plugin>.<sub> --component <component> 2>&1 | \
  grep '^{' | jq -s 'reduce .[] as $item ({}; . * $item)' > /tmp/collected.json

# Feed to policy
lunar policy dev <plugin>.<check> --component-json /tmp/collected.json
```

#### 4. Minimum coverage

**Collectors:**
- **Data present** — Component that HAS the relevant data. Verify correct, non-empty Component JSON is written with the expected paths and values.
- **No data** — Component that does NOT have the relevant data. Collector should write **nothing** — no empty arrays, no source metadata, no placeholder objects. The key should simply not exist.
- **Missing config** — Missing secrets or optional inputs. Collector should `exit 0` with a stderr message.

**Policies:**
- **Pass** — Component where all conditions are met. Check should PASS.
- **Fail** — Component where conditions are NOT met. Check should FAIL (not error, not skip).
- **Skip** — Component where the guardrail category doesn't apply (e.g. a Go policy on a Python repo). Check should SKIP gracefully.
- **Edge cases** — Missing fields, unexpected values, empty data. Should not crash.

#### 5. What you can do in cronos

The `pantalasa-cronos` environment is a sandbox — you have full freedom to:
- **Add files or dependencies to existing components** (e.g. add a `go.mod`, Terraform files, Dockerfiles, GitHub Actions workflows)
- **Create entirely new components** if none of the existing ones fit your testing needs
- **Install any open-source software** needed to test the plugin thoroughly
- **Create PRs on component repos** to test PR-context collectors/policies
- **Modify GitHub Actions workflows** to add CI steps (e.g. SBOM generation, security scans)

Don't worry about breaking things — cronos exists specifically for this. Clean up test branches when done.

#### 6. CI collectors must be tested on cronos

If the plugin includes a CI collector (hooks like `ci-after-job`, `ci-before-command`, etc.), it **must** be tested on the `pantalasa-cronos` demo environment with real CI runs. Local simulation is not sufficient — CI hooks only fire during actual CI runs with Lunar instrumentation active.

**Step-by-step cronos testing process:**

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

2. **Modify a component to use your tool in CI** — Clone a component repo (e.g. `pantalasa-cronos/backend`), add a CI step that runs your tool with report output:
   ```yaml
   # Example: adding gitleaks to .github/workflows/ci.yml
   gitleaks:
     runs-on: cronos
     steps:
       - uses: actions/checkout@v4
       - name: Install & Run
         run: |
           curl -sSfL <tool-download-url> | tar xz -C /usr/local/bin
           <tool> scan --report-path report.json
   ```
   Push to trigger the CI workflow. The lunar agent on the `cronos` runner traces commands and feeds data to collectors.

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
   The `components_latest` materialized view may lag — query the `components` table directly with the specific `git_sha` for immediate results.

5. **Screenshot the dashboard using Playwright MCP** — Use the Playwright MCP server to capture proof that everything works end-to-end in the real system. These screenshots are **required** evidence for the PR.

   Screenshots to capture:
   - **Component JSON page** (`/d/lujsqdc/component-json?var-component=<name>`) — expand the tree to show your collector's category data (e.g. `lang.cpp`)
   - **Component details page** (`/d/aecnnrn714em8d/component-details?var-component=<name>&var-pr=0`) — scroll the checks table to the rows showing the specific policy checks from your plugin (e.g. `html.htmlhint-clean`, `html.stylelint-clean`). The screenshot must show the checks we care about, not just the top of an empty or unrelated table.
   - **Collectors listing** (`/d/zzznoc11btoga/collectors-listing`) — your collector shows runs > 0

   Playwright MCP flow:
   1. Read Grafana credentials from `~/.bender/grafana-credentials`
   2. Use `browser_navigate` to go to `https://cronos.demo.earthly.dev/login` (or `lunar.demo.earthly.dev`)
   3. Use `browser_type` / `browser_click` to log in with the credentials
   4. Navigate to each dashboard URL above
   5. Use `browser_snapshot` and `browser_screenshot` to capture the page
   6. For JSON page: click tree nodes to expand your data section, then screenshot
   7. For component details: scroll to the policy checks section, then screenshot

   Note: Dashboard UIDs differ between environments. Query `/api/search?type=dash-db` to find UIDs.

   Upload screenshots to the PR comment as image attachments — they serve as proof that the collector and policies are working in the real system.

6. **Clean up** — Remove test files from the component repo after verifying results.

**Cross-org auth for pantalasa-cronos:**
```bash
GH_TOKEN=$(bender-gh-token pantalasa-cronos) gh <command> --repo pantalasa-cronos/<repo>
# Or for git operations:
git remote set-url origin "https://x-access-token:$(bender-gh-token pantalasa-cronos)@github.com/pantalasa-cronos/<repo>.git"
```

### Post test results on the PR

After testing, comment on the PR documenting what you tested and the results. **Include Playwright screenshots** from the cronos dashboard as proof.

```markdown
## Test Results

### Results

| Test case | Check | Result | Notes |
|-----------|-------|--------|-------|
| Positive (data present) | check-name | ✅ PASS | Correct output |
| Negative (no data) | check-name | ⏭️ SKIP | Skips gracefully |
| Edge case (missing field) | check-name | ⏭️ SKIP | No error |

### Component JSON Output

Include the actual component JSON output showing the collected data. This proves the collector
is writing the correct paths and values.

```json
{
  "lang": {
    "<language>": {
      "...collected data..."
    }
  }
}
```

### Edge cases verified:
- ✅ Missing API key → graceful exit 0
- ✅ Empty input data → no Component JSON written
- ✅ Malformed data → handled without crash

### Dashboard screenshots (from cronos)
- Component JSON showing `.lang.<language>` data: [screenshot]
- Component details page with checks table scrolled to show YOUR plugin's checks: [screenshot]
```

Upload the Playwright screenshots as GitHub comment image attachments. These are required proof that the plugin works end-to-end in the real system — not just in local `lunar collector dev` / `lunar policy dev` tests.

### A note on unit tests

Unit tests are not required and should **not** be committed. The primary way to validate collectors and policies is `lunar collector dev` / `lunar policy dev` locally and testing on cronos. If you find unit tests helpful for debugging complex logic during development, that's fine — just don't include them in the PR. Delete them before committing.

### Lint before pushing

Run the linter locally before committing to avoid back-and-forth CI failures:

```bash
earthly +lint
```

This validates README structure, YAML manifest fields (`display_name`, `long_description`, `category`, `status`, `keywords`), and other conventions. Fix any errors before pushing.

### Push implementation

Commit and push the implementation to the same PR branch. CI will run automatically. Fix any CI failures. Check for merge conflicts with main — if any exist, resolve them immediately (`git fetch origin main && git merge origin/main`). Do NOT leave a PR with merge conflicts.

### Then wait for approval

Claude will automatically review the PR when it's opened (or converted from draft). Address its inline comments, but **use judgment** — Claude sometimes flags things that aren't real issues. If a comment is wrong or irrelevant, reply explaining why and resolve the thread. When you've addressed a valid comment (pushed a fix), resolve that thread too. Don't leave conversations hanging.

You can request a re-review by commenting `@claude review once` on the PR, but **be mindful of costs** (~$15-25 per review). Only request a re-review when there have been significant code changes — e.g., after initially implementing code for a spec-only PR, or after a major refactor. For minor fixes (typos, small bug fixes, addressing review feedback), skip the re-review.

**Implementation review may trigger spec changes.** Reviewers may ask you to adjust the YAML manifest, README, or Component JSON paths even after implementation is added. This is normal — make the changes. **Re-test after significant changes** (logic changes, new assertions, changed Component JSON paths). A quick `lunar collector dev` or `lunar policy dev` run is enough — post updated results on the PR if the previous results are now stale.

Wait for the **requester** to approve the implementation (or merge directly). The requester is the implementation reviewer.

**While waiting:**
- Fix CI failures automatically.
- Address review comments. Push fixes. Reply to reviewers on the PR.
- **Do not merge** until the requester approves or merges directly.

---

## Merge

### Pre-merge checklist

- [ ] CI is green
- [ ] Claude review comments addressed
- [ ] **Requester approved** (or is merging directly)
- [ ] Test results posted on PR
- [ ] No unresolved review threads / suggestions

### Merge

Squash-merge the PR and delete the branch.

### Add to cronos

If this is a **new** collector or policy, it needs to be added to `pantalasa-cronos/lunar/lunar-config.yml`. Existing plugins that are already referenced will pick up changes from `@main` automatically.

**Testing a branch (before merge):** Reference your branch temporarily:

```yaml
- uses: github://earthly/lunar-lib/collectors/<name>@<branch>/<feature>
```

**After merge:** Update the reference to `@main`:

```yaml
- uses: github://earthly/lunar-lib/collectors/<name>@main
```

Don't leave branch references in the cronos config after merging.

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
| Using `c.succeed()` | There is no `c.succeed()` method. | Checks auto-pass if no assertions fail. Just don't call anything. |

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
| Starting implementation before second reviewer approves | The spec may change significantly during review. Implementation effort is wasted. | Wait for the second reviewer to approve the spec before implementing. |
| Using `git add .` or `git add -A` | Stages unintended files (test configs, temp files, etc.). | Always `git add` specific directories: `git add collectors/<name>/` or `git add policies/<name>/`. |
| Merging without requester's approval | The requester reviews implementation and must approve (or merge directly) before merging. | Wait for the requester's approval on the implementation. |
| Not posting test results on the PR | Reviewers need evidence, not trust. | Always post a test results comment with the template from this playbook. |
| Ignoring Claude review feedback | Claude auto-reviews open PRs. Unresolved comments slow down human review. | Address or reply to every Claude review comment before requesting human review. |

### Docker images

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Using `earthly/lunar-scripts:1.0.0` | Legacy image. | Use `earthly/lunar-lib:base-main` or `earthly/lunar-lib:<name>-main`. |
| Using `native` for code collectors | Code collectors must run in a container. | Use `earthly/lunar-lib:base-main` or a custom image. |
| Committing a temporary image tag | The tag won't exist after your test branch is cleaned up. | Always use `-main` tag in committed code. |
| Adding an Earthfile but not wiring it into the root `+all` target | CI builds and pushes images via `earthly --push +all`. If your Earthfile's `+image` target isn't listed in the root Earthfile's `+all` target, CI will never build or push your image. | Add `BUILD --pass-args ./<type>/<name>+image` to the `+all` target in the root Earthfile. |

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

