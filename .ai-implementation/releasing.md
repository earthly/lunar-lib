# Releasing lunar-lib

Step-by-step guide for performing a lunar-lib release. Only run a release when a human explicitly asks for one.

> **Permissions:** Requires `git push` access (SSH/GPG keys or token auth). AI agents should use `required_permissions: ["all"]`.

---

## Overview

A lunar-lib release produces **versioned Docker images** for every collector, policy, and cataloger plugin. The release process:

1. Creates a branch + tag named `vX.Y.Z` from the current `main` HEAD
2. Rewrites all plugin manifests and starter-pack configs to pin the version
3. Pushes to origin — CI builds and publishes images to Docker Hub
4. Consumers can then pin `@vX.Y.Z` in their Lunar configs

```text
main (HEAD) → release script → branch vX.Y.Z + tag vX.Y.Z → CI → Docker images pushed
```

> **Dogfood vs. cronos — two different environments.** lunar-lib plugins are *dogfooded* continuously: the internal dogfood hub tracks `@main` and runs them against Earthly's own repositories, so a change is exercised in real conditions the moment it merges — before any release is cut. **cronos is a separate demo/QA environment** (a synthetic repo fleet) pinned to release versions — it is **not** the dogfood hub. A release pins the new `@vX.Y.Z` images on cronos (Step 7) and verifies them there (Step 8); the dogfood hub needs no release-time action since it already tracks `@main`.

### What gets published

Every plugin with an `+image` target in its Earthfile gets a Docker image on Docker Hub:

- `earthly/lunar-lib:{plugin-name}-vX.Y.Z` — one per collector/policy/cataloger
- `earthly/lunar-lib:base-vX.Y.Z` — the shared base image

The full list of images is defined in the root `Earthfile` under the `+all` target.

---

## Prerequisites

Before running a release, verify:

| Check | How |
|-------|-----|
| You're on `main` | `git rev-parse --abbrev-ref HEAD` → `main` |
| `main` is up to date | `git pull origin main` |
| Working tree is clean | `git status --porcelain` → empty |
| HEAD is what you want to release | `git log --oneline -5` — confirm the latest commits are what the human expects |
| No existing branch/tag for this version | `git tag -l vX.Y.Z`, `git branch -a \| grep vX.Y.Z`, and `git ls-remote --refs origin \| grep vX.Y.Z` → all empty |
| CI is green on main | `gh pr checks` or check the latest workflow run on main |

### Version numbering

- Format: `vX.Y.Z` (v-prefixed semver, e.g. `v1.0.6`)
- Check the latest tag: `git tag --sort=-creatordate | head -5`
- You propose the version — see Step 1 below.

---

## Release Steps

### Step 1: Propose a version and get sign-off

Analyze what changed since the last release and propose the next version:

1. Find the last release tag: `git tag --sort=-creatordate | grep '^v' | head -1`
2. List changes since that tag: `git log --oneline <last-tag>..HEAD`
3. Determine the bump:
   - **Patch** (`v1.0.5` → `v1.0.6`): bug fixes, doc updates, minor improvements
   - **Minor** (`v1.0.5` → `v1.1.0`): new collectors/policies, new features, non-breaking changes
   - **Major** (`v1.0.5` → `v2.0.0`): breaking changes to manifest format, SDK, or plugin interface
4. DM the person who requested the release (via Slack) with your proposal:
   - The proposed version number
   - A summary of what's included (e.g., "3 new collectors, 2 bug fixes")
   - Current HEAD (`git log --oneline -1`)
5. Wait for their sign-off before proceeding.

**Do not proceed without explicit confirmation of the version number.**

### Step 2: Run the release script

```bash
cd /path/to/lunar-lib    # must be repo root
./scripts/release.sh vX.Y.Z
```

The script handles everything:

1. **Validates** the version format (must match `^v[0-9]+\.[0-9]+\.[0-9]+$`)
2. **Checks** working tree is clean, no duplicate branch/tag
3. **Creates** local branch `vX.Y.Z`
4. **Rewrites manifests** — all `lunar-*.yml` files: changes `earthly/lunar-lib:*-main` → `earthly/lunar-lib:*-vX.Y.Z`
5. **Rewrites starter packs** — all `starter-packs/**/*.yml` files: changes `@<anything>` → `@vX.Y.Z`
6. **Verifies** no unrewritten `-main` image refs or unpinned starter-pack refs remain
7. **Commits** with message `Pin images for vX.Y.Z`
8. **Creates** git tag `vX.Y.Z`
9. **Pushes** both the branch and tag to origin
10. **Restores** your previous branch

If the script exits non-zero, do **not** re-run it. See [Troubleshooting](#troubleshooting).

### Step 3: Monitor CI

The push to a `v*.*.*` branch triggers the CI workflow (`.github/workflows/ci.yml`):

```bash
# Wait for CI to start, then watch
gh run list --branch vX.Y.Z --limit 3
gh run watch <run-id>
```

CI runs three jobs:
- **+test** — runs `earthly --ci +test`
- **+lint** — runs `earthly --ci +lint`
- **+all (build-and-push)** — builds every plugin image and pushes to Docker Hub with the `vX.Y.Z` tag

All three must pass. If any fail:

```bash
gh run view <run-id> --log-failed
```

Read the logs, diagnose, and report to the human. **Do not attempt fixes on the release branch** — fixes should go to `main`, and a new release cut after they land.

### Step 4: Verify images exist

After CI passes, confirm the images were published to Docker Hub. **Do not pull them** — just check they exist via the API (no auth needed for public images):

```bash
# List all tags matching this version
curl -s "https://hub.docker.com/v2/repositories/earthly/lunar-lib/tags/?name=vX.Y.Z&page_size=100" | jq '.count, [.results[].name]'
```

Verify the count matches the number of `+image` targets in the root `Earthfile` `+all` target (base image + all plugins). If any are missing, check the CI build logs for that specific plugin.

### Step 5: Create a GitHub Release with release notes

After CI passes and images are verified, create a GitHub Release to document what shipped:

1. **Generate categorized release notes** by analyzing commits since the previous tag:

   ```bash
   git log --oneline <previous-tag>..vX.Y.Z
   ```

2. **Categorize changes** into these sections:
   - **New Collectors** — newly added collectors (include status: beta, experimental, stable)
   - **New Policies** — newly added policies (include status)
   - **Fixes** — bug fixes to existing collectors/policies
   - **Improvements** — enhancements, performance, refactors
   - **Other** — docs, CI, tooling changes

   To determine plugin status, check the plugin's manifest (`lunar-collector.yml` or `lunar-policy.yml`) for any `status` or `maturity` field. If absent, default to "stable" for plugins with tests and "beta" for new plugins in their first release.

3. **Create the release:**

   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --notes "$(cat <<'EOF'
   ## New Collectors
   - **plugin-name** (beta) — brief description

   ## New Policies
   - **plugin-name** (stable) — brief description

   ## Fixes
   - Fix description (#PR)

   ## Improvements
   - Improvement description (#PR)
   EOF
   )"
   ```

   **Important:** When running this, the `EOF` delimiter must be at column 0 (no leading spaces). The indentation above is for markdown readability only — in your actual shell command, left-align `EOF`.

   Omit empty sections. Link PR numbers where applicable.

### Step 6: Notify

**On success:** Post to `#team-eng` on Slack for visibility:
- Release tag: `vX.Y.Z`
- Summary of what's new (new collectors/policies, key fixes)
- Link to the GitHub Release
- How consumers pin it: `@vX.Y.Z` in their `lunar-config.yml`

```bash
# Post to #team-eng
curl -s -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel":"#team-eng","text":"lunar-lib vX.Y.Z released: <github-release-url>\n\n<summary>"}'
```

**On failure or questions:** DM the person who requested the release directly — don't spam the team channel with problems.

### Step 7: Update cronos to the new version

After a successful release, update the cronos staging environment to reference the new version:

1. **Open the cronos lunar config** — the repo is `pantalasa-cronos/lunar`, in a **different GitHub org**, so `git`/`gh` need a `pantalasa-cronos` token (the default `earthly` token 404s here):

   ```bash
   # Clone if missing; the local clone dir is ~/repos/pantalasa-cronos-lunar
   TOKEN="$(bender-gh-token pantalasa-cronos)"
   git clone "https://x-access-token:${TOKEN}@github.com/pantalasa-cronos/lunar.git" ~/repos/pantalasa-cronos-lunar 2>/dev/null || true
   cd ~/repos/pantalasa-cronos-lunar
   git remote set-url origin "https://x-access-token:${TOKEN}@github.com/pantalasa-cronos/lunar.git"
   git checkout main && git pull origin main
   ```

   The config is split across the repo **root**: `lunar-config.yml` holds top-level
   settings, while the plugin `uses:` pins live in the numbered files under
   `lunar-config.d/` (e.g. `20-catalogers.yml`, `30-collectors.yml`,
   `50-policies.yml`). The `@v<version>` refs you're bumping are in `lunar-config.d/`
   — `lunar-config.yml` itself has none.

2. **Update pinned version references:**

   Replace all `@v<old-version>` references with `@vX.Y.Z`. The pins live under
   `lunar-config.d/`, so run the sed over that directory:

   ```bash
   sed -i 's|@v<old-version>|@vX.Y.Z|g' lunar-config.d/*.yml
   # verify nothing on the old version is left behind (should print nothing):
   grep -rn '@v<old-version>' lunar-config.d/ lunar-config.yml
   ```

   This updates collectors, policies, and catalogers that were pinned to the previous release. Plugins still on `@main` are tracking the main branch and don't need changes.

3. **Commit and push:**

   ```bash
   git add lunar-config.d/ lunar-config.yml
   git commit -m "Pin cronos lunar config to vX.Y.Z"
   git push origin HEAD:main
   ```

4. **Verify the `Sync Lunar Config` workflow passes** in `pantalasa-cronos/lunar` — it runs `lunar hub pull` to push the updated manifest to the hub. If it fails, the hub won't pick up the new configuration.

   > **Transient failures:** the `lunar hub pull` step intermittently dies with `failed to receive server stream: rpc error: code = Unavailable ... connection reset by peer`. If the log shows every plugin resolved (`fetching remote plugin: ...`) and only the hub stream errored, it's a transient infra blip — **not** a bad config — so just re-run it: `GH_TOKEN=$(bender-gh-token pantalasa-cronos) gh run rerun <run-id> --repo pantalasa-cronos/lunar --failed`.

**Note:** Only update `@v<old>` → `@vX.Y.Z`. Leave two other ref kinds untouched: `@main` refs (development plugins being tested, or plugins that intentionally track latest) and any commit-SHA pins (`@<40-char-sha>`, e.g. a plugin held at a specific fix). The `@v<old>`-only sed already skips both — but eyeball the diff to confirm it moved only the version pins you expected.

### Step 8: Verify the release on cronos

Bumping the pins (Step 7) only tells the hub *which* images to use — it doesn't prove they work. cronos now runs the released `@vX.Y.Z` images against its repo fleet, so confirm they actually collect and render checks before you call the release done.

1. **Wait for the manifest to land.** The `Sync Lunar Config` workflow from Step 7 must finish — that's what pushes the new manifest to the hub. Until it's green, the hub is still on the old version.

2. **Let a collection cycle run.** Collectors, policies, and catalogers run on the hub's schedule (or on a repo event). Give it a cycle so the new version's plugins execute against the cronos repos. Pushing a trivial commit to one component is a quick way to force a fresh run instead of waiting for the cron.

3. **Check the cronos Grafana dashboard.** On the component-details **Checks** tab, confirm the collectors ran and the checks rendered for the components touched by this release. Spot-check anything new or changed: a new collector should be producing its checks; a changed policy should reflect the new behavior.

4. **Wait for the checks to fully settle before declaring green.** A check showing an asterisk (`*`), or a *stale/pending* disclaimer at the bottom of the panel, means the view is still settling — refresh/poll until it clears. Database counts (snippet runs finished, `checks` populated at the new git SHA) are **necessary but not sufficient**; the dashboard UI itself must be settled before you trust it.

5. **If the markers don't clear after a reasonable wait, treat it as a possible pipeline problem and flag it** — don't report a half-settled dashboard as a passing release. A release that publishes images but can't produce checks on a real hub is not done.

> Pinning is exactly when a phantom image ref surfaces — a plugin whose `default_image` points at an image that `+all` never built (see Step 4). Those resolve fine on `@main` but 404 once pinned to `@vX.Y.Z`, and the dashboard is where you'll catch the missing checks.

---

## What the CI Workflow Does

The CI workflow (`.github/workflows/ci.yml`) triggers on:
- Pushes to `main`
- Pushes to branches matching `v[0-9]*.[0-9]*.[0-9]*`
- PRs targeting `main`

For release branches, the `build-and-push` job:
1. Normalizes the branch name (replaces `/` with `-`)
2. Logs into Docker Hub (using `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets)
3. Runs `earthly --ci --push +all --VERSION "vX.Y.Z"`
4. Earthly builds every `+image` target listed in the root `Earthfile` `+all` target, passing `VERSION` as a build arg
5. Each plugin's Earthfile uses `SAVE IMAGE --push earthly/lunar-lib:{name}-$VERSION`

On `main` branch only, CI also pushes images tagged with the short git SHA (first 8 chars).

### Required secrets (configured in GitHub repo settings)

| Secret | Purpose |
|--------|---------|
| `EARTHLY_TOKEN` | Earthly Cloud auth for builds |
| `DOCKERHUB_USERNAME` | Docker Hub login |
| `DOCKERHUB_TOKEN` | Docker Hub auth |
| `SLACK_BOT_TOKEN` | Slack bot token for posting to #team-eng (agent runtime env, not a GitHub secret) |

The CI secrets (`EARTHLY_TOKEN`, Docker Hub) are configured in GitHub repo settings. `SLACK_BOT_TOKEN` is an agent runtime credential available in the agent's shell environment.

---

## File Changes Made by the Release Script

### Manifest rewrites (`lunar-*.yml`)

Every collector, policy, and cataloger has a manifest file (e.g., `collectors/golang/lunar-collector.yml`) with a `default_image` field. The script changes:

```yaml
# Before (on main)
default_image: earthly/lunar-lib:golang-main

# After (on release branch)
default_image: earthly/lunar-lib:golang-v1.0.6
```

### Starter-pack rewrites

Starter-pack config files in `starter-packs/` reference plugins by GitHub URL. The script changes:

```yaml
# Before
- uses: github://earthly/lunar-lib/collectors/golang@main

# After
- uses: github://earthly/lunar-lib/collectors/golang@v1.0.6
```

All `@<ref>` suffixes are rewritten to `@vX.Y.Z`, regardless of what they pointed to before.

---

## Troubleshooting

### Script fails: "branch/tag already exists"

Someone (or a previous failed attempt) already created that version. Check:

```bash
git branch -a | grep vX.Y.Z
git tag -l vX.Y.Z
git ls-remote --refs origin | grep vX.Y.Z
```

If it's a leftover from a failed run:
1. **Ask the human before deleting anything** — don't assume
2. Clean up: `git branch -d vX.Y.Z`, `git tag -d vX.Y.Z`, `git push origin --delete vX.Y.Z` (both ref types)
3. Then re-run the script

### Script fails: "working directory is not clean"

Run `git status` and resolve. Either commit, stash, or discard changes — but ask the human first if there are meaningful uncommitted changes.

### Script fails: "unrewritten -main image references"

The script verifies all `lunar-*.yml` files had their `-main` refs rewritten. If some slipped through, it means a manifest uses a non-standard image reference pattern. Investigate the offending file and fix the regex or the manifest.

### CI fails on the release branch

1. Read the failure logs: `gh run view <run-id> --log-failed`
2. **Do not push fixes to the release branch.** The release branch is a snapshot.
3. Fix the issue on `main`, get it merged, then cut a new release from the updated `main`.
4. Clean up the failed release: delete the tag and branch (with human approval).

### Images not appearing on Docker Hub

- CI must finish the `build-and-push` job fully (not just test/lint)
- Check the Docker Hub login step didn't fail silently
- Verify the Earthfile `+all` target includes the expected plugin

### "I need to add a new plugin to the release"

If a new plugin was merged to `main` after the release but before you noticed, you need a new release — there's no way to retroactively add images to an existing release tag. Bump the patch version and cut again.

---

## Release History

For reference, recent releases and their patterns:

| Version | Date | Commits since previous |
|---------|------|----------------------|
| `v1.0.5` | 2026-03-25 | 4 commits from v1.0.4 |
| `v1.0.4` | 2026-03-20 | — |
| `v0.1.0` | 2026-01-15 | Initial release |

Check the latest state with: `git tag --sort=-creatordate | head -5`
