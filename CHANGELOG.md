# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `grype` and `trivy` collectors: `container-scan` and `container-rescan` scan
  every image the component pushed, not just the last one. `.container_scan`
  gains `images[]` (per-image counts), `findings[].image` and `errors[]`;
  `container_image` accepts a comma-separated list. The `container-scan`
  `max-severity` check names the image(s) on each failing line.

- `grype` and `trivy` collectors: `container-scan` and `container-rescan` now
  declare `size: large`, since pulling an image can exceed the default 1Gi
  ephemeral-storage limit. `size:` on the `uses:` line does not reach a
  plugin's sub-collectors yet (ENG-1695), so it lives in the manifest (#301).

### Security

- All plugin images: OS packages are now upgraded at build time (`apk upgrade`
  on the shared alpine base image, `apt-get upgrade` on the five debian-based
  images), clearing the fixable critical OpenSSL CVEs (CVE-2026-63073,
  CVE-2026-75803) every published image carried, and the lunar-scripts base is
  pinned to 1.1.6 (lunar CLI 2.10.0, which raises the gRPC message cap to
  16 MiB). `nodejs` and `license-origins` move to Node 22.23.2 and npm 12.0.2
  for the fixable criticals in Node and in npm's vendored `tar` (#300).

## [1.14.2] — 2026-09-01

### Added

- `backstage` collector + policy: transitive domain referential integrity. A
  Backstage `Component` reaches a domain only through its `System`, so on the
  usual one-`Component`-per-repo catalog file `domain-exists` had nothing to
  read and passed vacuously — a component whose system pointed at a missing
  domain was indistinguishable from a healthy one. The collector now follows
  `spec.system` one hop further to that System's own `spec.domain` and records
  `.refs.system_domain = {name, exists, via_system}`; the new
  `system-domain-exists` check consumes it and names the offending System, since
  that's whose catalog file needs fixing. `domain-exists` is unchanged (#299).

## [1.14.1] — 2026-08-31

### Added

- `backstage` collector: `ref_lookup` input selects which catalog endpoint
  resolves each declared `spec.domain` / `spec.system` reference — `by-name`
  (default, unchanged behavior) or `by-query`. Some deployments authorize only
  the catalog search endpoint: a gateway in front of Backstage can expose
  `/catalog/entities/by-query` while rejecting `/catalog/entities/by-name/...`
  outright, and then every reference lookup fails however correct the auth is,
  recording an `error` per reference that reads like an outage rather than a
  misconfiguration. `by-query` is the same endpoint the `backstage` *cataloger*
  already uses, so an instance the cataloger can read supports it. Both modes
  write an identical `.refs` shape, so no policy changes are needed, and
  `ref_lookup` composes with `auth_mode` and `api_path_prefix`. Because
  `by-query` reports "no match" as an empty result set, a `200` whose body is
  not parseable JSON records `{name, error}` rather than collapsing into
  `exists: false` — a gateway login page must not read as a missing domain
  (#297).

## [1.14.0] — 2026-08-28

### Added

- `ticket-coverage` collector and policy (experimental): record and score what
  share of a component's recent pull requests referenced an issue-tracker
  ticket. Per-PR ticket checks only ever produce PR-scoped results, and every
  Lunar rollup filters on `pr IS NULL`, so a component with a spotless record of
  ticket-linked pull requests scored zero on a change-management initiative —
  indistinguishable on screen from everything-failing. Writing the metric on the
  default branch is what makes ticket adoption scoreable at all. The collector
  reads only Lunar's own data through the SQL API — no issue-tracker or Git
  platform call and no token — so it behaves the same on any Git platform, which
  is the substantive difference from the existing `jira` `ticket-history`
  sub-collector (#288).

- `codeql` collector (`monorepo-fanout`): new sub-collector that redistributes a
  monorepo's repo-wide CodeQL findings to its subdirectory components. A
  repo-scoped scan resolves to the repository, so its findings land on the
  repo-root component and every subcomponent evaluates as "No SAST scanning data
  found" despite having been scanned. This runs on the root once its collection
  settles and writes each subcomponent's own slice of the path-tagged findings
  onto that subcomponent at the same commit; a finding no component claims stays
  on the root. Attribution reuses Lunar's own change-detection rule (a
  component's explicit `paths:` plus the implicit patterns its name implies), so
  a monorepo whose components are scoped correctly for change detection needs no
  new configuration. The `after-json` hook is on `.sast.issues` rather than
  `.sast`, because the CLI sub-collector writes `.sast.native.codeql.cicd` for
  every `codeql` exec — so `.sast` is present on any repo where `codeql` merely
  ran, including runs that produce no SARIF. Target it at the repository root
  component and enable it alongside `cicd`, which writes the findings it fans
  out (#293).

- `backstage` collector: AWS SigV4 authentication for the referential-integrity
  lookups, for Backstage APIs fronted by AWS IAM auth (e.g. Amazon API Gateway)
  that reject Bearer tokens. Set `auth_mode: sigv4` plus `aws_region` (and
  `aws_service`, default `execute-api`); credentials resolve at runtime from the
  standard AWS chain — IRSA, EKS Pod Identity / ECS, EC2 instance profile, then
  the optional static `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` secrets — so
  they self-refresh with nothing to rotate. Brings the collector to parity with
  the `backstage` cataloger (#232); both run in the same snippet pods, so a
  single service-account role annotation covers both. An auth or
  credential-resolution failure never discards the parse and lint results — it
  is recorded as a per-reference `{name, error}` (#294).

- `backstage` collector: `api_path_prefix` input (default `/api`) — set it to an
  empty string when the Backstage catalog API is mounted at the root, e.g. behind
  an API gateway that strips the `/api` hop and returns 403/404 for
  `/api/catalog/entities`. Matches the same input on the `backstage` cataloger.
  This pairs with `auth_mode: sigv4` above: an IAM-fronted Backstage is usually
  behind Amazon API Gateway, which is exactly the shape that strips the hop, so
  the instances needing SigV4 are often the ones needing an empty prefix (#294).

- `sca` and `container-scan` policies (`max-severity`): new `ignore_unfixable`
  input (default `false`) narrows the failure to findings that carry an upgrade
  target, so an unfixable base-image or upstream advisory cannot hold a release
  gate closed indefinitely. It is applied after the threshold has already been
  crossed, so it can only turn a FAIL into a PASS and never manufactures a
  failure the default would not have raised. Unfixable findings are still
  collected and still visible in the Component JSON — the option changes the
  verdict, never what is recorded — and a summary-only scan fails as if the
  option were off and says why. Also collapses findings double-written when two
  scanners write the same path, keyed on CVE id, so a CVE is enumerated once
  rather than once per scanner (#289).

- Manifest snippet allow-list: the `meta` and `failureText` snippet fields are
  now accepted. Both landed in the hub on 2026-08-25, after the allow-list was
  transcribed, so a manifest setting either was rejected as an unknown key. The
  unknown-key error no longer asserts that the hub silently ignores the key —
  a false statement for a field the hub decodes fine, and one that would talk an
  author into deleting working configuration — and the allow-list records the
  upstream commit it was derived from so the next drift is auditable (#292).

### Changed

- `backstage` cataloger: components whose git repository does not exist are now
  skipped instead of catalogued, via the new `verify_repos` input (default
  `true`). A Backstage id annotation is a claim about a repo, not a fact, and
  Lunar does not validate repo existence when the catalog is saved — so a
  renamed, deleted or typo'd slug created a component with nothing behind it,
  which no collector or policy could ever run against. Skipped components are
  named in the run log. In practice this stays off until the new optional
  `GH_TOKEN` secret is set: without it the cataloger logs one line and writes
  every component as before, so upgrading changes nothing until you opt in.
  The host is read from each component id, so a catalog spanning github.com and
  any number of GitHub Enterprise Server hosts needs no extra configuration, and
  each host is verified independently — a host that can't be checked (bad
  credentials, unreachable, or a forge that isn't GitHub) leaves its own
  components untouched without affecting the rest. Lookups are batched ~100
  repos per GraphQL request rather than one request per component. A component
  is dropped only on an explicit `NOT_FOUND` from GitHub, never on a null
  `data` field alone — GitHub also nulls a field for `FORBIDDEN` (a classic PAT
  not SSO-authorized for a SAML org, where the repo exists and the token simply
  cannot see it) and for a partial `SERVICE_UNAVAILABLE` (#295).

- `backstage` cataloger: an explicit empty `component_id_prefix` is no longer
  clobbered back to `github.com/`. It used `:-` rather than `-`, so setting it
  to `""` silently kept the default and double-prefixed ids whose annotation
  value already carried a host — which made a multi-host catalog impossible to
  express. Same bug ENG-1105 fixed for `tag_prefix` (#295).

- `sca` and `container-scan` policies (`max-severity`): a failing check now
  emits the severity headline plus one assertion per offending finding, most
  severe first, instead of a truncated list ending in "+N more (see component
  JSON for full list)". That pointer used internal jargon, so it meant nothing
  to the developer reading the PR comment; the hub already truncates the display,
  so the policy needs no cap of its own. A summary-only collector with no
  per-finding detail still emits the headline alone. Also wires `policies/sca`
  and `policies/container-scan` into the root `+test` target — both had test
  suites CI was never running (#252).

### Fixed

- `claude`, `coderabbit` and `codeql` collectors: `runs_on` was nested under
  `hook:` in five sub-collectors, where it does nothing. `runs_on` is a
  snippet-level field; the hook mapping has no such key, and because plugin
  manifests are not decoded with unknown-key rejection it was dropped silently
  and then replaced by the `[prs, default-branch]` default. All five were
  running in both contexts while the manifest said otherwise. `claude`
  (`code-reviewer`, `run-code-review`) and `coderabbit` (`code-reviewer`) now
  declare `runs_on: [prs]` at snippet level and **stop running on
  default-branch commits** — they read pull request review data, and on a
  default-branch commit there is no pull request. The two `codeql`
  sub-collectors drop the key instead: GitHub Code Scanning covers the default
  branch and `github-app.sh` queries check-runs for any commit, so both should
  run in both contexts and the key was only ever a copy of the semgrep
  pattern, whose PR-only reasoning does not apply. codeql behaviour is
  therefore unchanged. A new `scripts/validate_manifest_schema.py` runs in
  `+lint` and now fails the build on any key a plugin manifest puts outside
  the snippet or hook schema, naming the file, sub-snippet, key and line
  (#291).

### Security

- `gitleaks` collector: the raw scanner report is no longer stored with detected
  secrets in plaintext. Both sub-collectors shipped the report to
  `.secrets.native.gitleaks.{auto,cicd}.report`, and gitleaks puts the detected
  credential in that report's `Secret` and `Match` fields — so a secret scan
  produced a stored copy of the very secrets it found. The normalized
  `.secrets.issues` / `.secrets.cicd` projections were always safe. `scan.sh`
  now passes `--redact` and then verifies the report really is redacted rather
  than trusting the flag, dropping it if not; `cicd.sh` strips `.Secret` and
  `.Match` with `jq`, and collects the raw report only when it parses as a
  gitleaks JSON array that was successfully stripped. Both paths degrade to
  losing raw detail, never to leaking (#290).

## [1.13.0] — 2026-08-18

### Added

- `package-registries` collector and `registry-provenance` guardrails in the
  `dependencies` policy: verify that repositories resolve dependencies through
  an approved package registry rather than straight from a public index. The
  collector reads package-manager configuration already committed to the repo
  and normalizes the resolved registry per ecosystem into a new `.dependencies`
  category, covering npm, pip, Maven, Gradle, RubyGems and NuGet — token-free,
  Python stdlib only, and registry locations only (`_authToken` lines are
  skipped and URL userinfo is stripped, so credentials are never emitted). An
  ecosystem in use that declares no registry still resolves from its public
  default, so that default is recorded with `is_default: true` rather than
  omitted — otherwise the guardrail would pass the most common violation (#286).

### Changed

- **BREAKING** — `pagerduty` collector: `oncall` is now the code-hook
  sub-collector that runs on pull requests and the default branch, and the daily
  cron variant moves to `oncall-cron`. This matches the `trivy`/`grype` split
  philosophy, where the event-driven collector takes the base name. Both share
  the same script and write the same normalized `.oncall.*` output. An import
  pinning `include: [oncall]` for the daily cron must change to
  `include: [oncall-cron]` (#283).

- `golang` collector (`golangci-lint`): declares `size: large`, raising the
  memory limit from 512Mi to 2Gi. `golangci-lint` runs `go mod download` and
  then type-checks every package, so its peak memory scales with the module and
  overran the default profile on larger Go repos; the container was OOMKilled,
  the run recorded as internal-error, and that commit's lint data simply lost.
  Mirrors the sibling `grype` and `trivy` collectors. The `golangci-lint-ci`
  sub-collector stays on the default profile — it runs native on the CI runner
  and only parses the user's existing JSON output (#282).

### Fixed

- `docker` collector (`hadolint`) and the `container` policies: a component that
  has never built a container no longer materializes a `.containers` object. The
  "no Dockerfiles found" path wrote an empty `.containers.lint_results`, and
  object presence in the Component JSON is the detection signal. Downstream, the
  container policies gated on `.containers.*` with a bare `return`, producing a
  check with zero assertions — which the SDK resolves to PASS, indistinguishable
  from a check that genuinely succeeded. All 8 now `skip()` with a reason. The
  empty-vs-absent distinction is preserved: Dockerfiles present and hadolint
  clean still writes `[]` and genuinely passes (#287).

- `trivy` and `grype` collectors (`container-scan`): image scans no longer skip
  on every pull request. The image to scan is resolved from the docker
  collector's pushed-image record via `lunar component get-json`, but the lookup
  was unqualified — the Hub resolves that to the default-branch snapshot
  (`WHERE pr IS NULL`), so a PR run read main's Component JSON, never saw the
  image the PR had just pushed, and skipped with "No pushed container image to
  scan" (which in turn made the `container-scan` policy report no scan data). In
  PR context the lookup is now pinned to the commit being scanned (`--pr`, plus
  `--git-sha` to select the exact commit rather than the PR's latest). The
  default-branch lookup is deliberately unchanged: the `container-rescan` cron
  is given the latest *ingested* main commit, which may not have been collected
  yet, so pinning there would resolve nothing and silently stop the re-scan
  (#284).

## [1.12.2] — 2026-08-11

### Changed

- `github-org` cataloger: new `max_repos_per_visibility` input (default 10000)
  raises the per-visibility fetch ceiling, and a fetch that returns exactly the
  ceiling now warns loudly instead of silently cataloguing a partial org. There
  was never a 1000-repo limit — `gh repo list` paginates over the GraphQL API
  and the write loop chunks every entry to the hub — but the `--limit` ceiling
  was applied with no signal. The catalog is also emitted in byte-bounded,
  sorted batches (#279).

- `pagerduty` collector: transient PagerDuty API errors (429, 5xx, timeout,
  connection refused) are retried with backoff and `Retry-After` handling
  instead of failing the call, fixing flaky `oncall` policy results. The caller
  contract is unchanged (#281).

- `vcs` policy: failure text and documentation are now vendor-agnostic. The
  policy hardcoded "github" in user-facing text even though the `gitlab`
  collector populates the same `.vcs.*` schema, so failure messages and docs
  were misleading for GitLab-hosted repos. All 14 "data not found" messages now
  say "Ensure a VCS collector…", and `gitlab` joins `github` in
  `landing_page.requires` (#278).

### Fixed

- `backstage` collector: a multi-document `catalog-info.yaml` (several entities
  separated by `---`, e.g. a Component plus the APIs it provides) is now parsed
  correctly. `yq -o=json '.'` emits concatenated JSON objects on a multi-doc
  file — not valid JSON — so the lint threw and the collector wrote only
  `{valid: false, errors: [...]}` with no metadata or spec, and every downstream
  policy false-failed on a perfectly legal file. Every document is now linted,
  with each error tagged by document index and kind (#280).

## [1.12.1] — 2026-08-10

### Fixed

- `jira` collector (`ticket-from-json`): the after-json collector fired but
  never resolved the ticket on a real pull request. It read the Component JSON
  without `--pr`, and `get-json` defaults `--pr` to 0 with no environment
  fallback, so it returned the main-branch JSON — no `.vcs.pr.title` — and the
  collector skipped, leaving `.vcs.pr.ticket` unwritten and `ticket-present`
  failing. It now passes `--pr "$LUNAR_COMPONENT_PR"` (#277).

- Cataloger READMEs: corrected an invalid `uses:` scheme in the installation
  examples, and taught the README validator to check the cataloger `uses_path`
  scheme so it cannot recur (#276).

## [1.12.0] — 2026-08-07

### Added

- `gitlab` collector (`merge-request`, `repository`, `branch-protection`,
  `access-permissions`), producing the shared `.vcs.*` schema, plus a `.vcs.pr`
  producer/consumer split: `github` `pull-request` and `gitlab` `merge-request`
  populate `.vcs.pr.*`, and the `jira` `ticket-from-json` after-json consumer
  reads `.vcs.pr` — no `GH_TOKEN`, provider-agnostic. `branch-protection`
  normalizes approval rules, external status checks and push rules so the shared
  `vcs` policy evaluates GitLab data (13 of 14 checks pass;
  `require-branches-up-to-date` is GitHub-only). Validated against a live GitLab
  instance (#274).

- `backstage` cataloger: `include_*` / `exclude_*` inputs for `spec.type`,
  `spec.lifecycle`, and resolved domain and system, so a large catalog can be
  onboarded incrementally (one domain at a time) and trimmed of noise. Mirrors
  the `github-org` cataloger's allowlist/denylist pattern: comma-separated,
  empty disables, exclude wins over include. Filters run client-side because
  Backstage's `?filter=` has no negation, and they are kind-aware — Domain and
  System entities carry no type or lifecycle, so they always pass and the
  hierarchy survives when components are filtered down (#272).

### Changed

- `jira` collector: ticket references are now detected in the PR description as
  well as the title, and checked against Jira before one is collected. `ticket`
  and `ticket-history` read both fields from the same GitHub PR fetch and build
  a candidate list, best first — every bare reference in the title, then every
  keyword-anchored reference in the description (`Fixes ABC-123`,
  `Ticket: ABC-123`), then every bare reference in the description — and
  collect the first candidate Jira confirms exists. A title reference still
  wins, and PRs that keep their ticket in the body now collect
  `.vcs.pr.ticket` instead of nothing. Keyword anchoring matters because a
  description usually names several tickets and the first to appear is often a
  dependency rather than the PR's own; the new `ticket_keywords` input sets the
  vocabulary (GitHub's closing keywords plus `ticket`/`issue` by default).
  Skipping candidates Jira does not know keeps the permissive default
  `ticket_pattern` from collecting a token like `UTF-8` as the ticket, and the
  new `max_ticket_candidates` (default 5) bounds the lookups that costs. Both
  sub-collectors resolve through the same validated path, so the reuse count
  keys off the ticket that was actually collected. Only one ticket is
  collected — `.vcs.pr.ticket.id` is single-valued (#271).

- `jira` collector: Jira lookups now tell their failure modes apart. A
  transient failure — connection refused, timeout, `429`, `5xx` — is retried
  `jira_retries` times (default 3); if Jira is still unreachable the run keeps
  the ticket reference and records `.vcs.pr.ticket.tracker_error` =
  `unreachable`, so an outage does not misreport the PR as ticket-less. When
  every candidate is checked and none exists, that is recorded as `not_found`.
  Rejected credentials (`401`/`403`) are not retried and fail the run, since a
  bad token is a misconfiguration an operator has to fix rather than a property
  of the PR. The `ticket-valid` policy reads `tracker_error` and names the
  actual cause instead of guessing between them (#271).

- `backstage` collector: `metadata.tags` in `catalog-info.yaml` are validated
  against Backstage's own tag rules. The schema accepts any non-empty string,
  but the Backstage server rejects the whole entity at ingest unless each tag
  matches `isValidTag` (lowercase `[a-z0-9+#]` segments, dash-separated, 63
  chars or fewer) — so a tag like `hosting/internal` passed Lunar and only
  failed at registration with a confusing `'tags.0' is not valid`. Slashes,
  spaces, dots, uppercase, bad or edge dashes, over-length, non-string items and
  a non-list `tags` field now surface as errors naming the offending tag (#275).

### Fixed

- `nodejs` policy (`engines-pinned`): a project that correctly pins
  `engines.node` no longer false-fails. `lunar_policy`'s `assert_true` is a
  strict identity check (`v is True`), and the check passed it the truthy
  `engines.node` string (e.g. `">=18"`) instead of a bool, so the assertion
  could never pass on a real version constraint — it only ever "passed" by
  taking the missing-data path. The value is now coerced to a bool (#273).

## [1.11.0] — 2026-07-30

### Changed

- `container` policy (`stable-tags`): a base image tag is now considered stable
  when it *contains* a full `major.minor.patch` semantic version anywhere in the
  tag, so registry- or vendor-specific prefixes and suffixes are accepted (e.g.
  `v4-bpl-3.24.0`, `9.6.1-jdk25-alpine`, `26.0.1_8-jre-alpine`). Previously the
  tag had to be *exactly* a semver (optionally `v`-prefixed / `-`-suffixed),
  which flagged these pinned, immutable tags as unstable. Partial versions like
  `20` or `16.1` still fail (#270).

- `jira` collector: errors now fail the run with a non-zero exit code instead
  of silently exiting 0 — a missing `GH_TOKEN` secret, a failed GitHub
  PR-metadata fetch (both sub-collectors), a missing `psql` client, and a
  failed reuse-count query (`ticket-history`) all surface as failed runs.
  Normal-outcome skips (not in PR context, no ticket reference found, optional
  Jira validation not configured, no SQL API in hub-less dev) still exit 0. A
  failed Jira issue lookup also still exits 0, deliberately: the Hub discards a
  failed run's collected values, and that path must preserve the already
  collected ticket reference (#269).

### Fixed

- `jira` collector: the PR-metadata fetch built an invalid GitHub API URL for
  monorepo sub-path components (`github.com/<owner>/<repo>/<path>`), so
  `ticket` and `ticket-history` collected nothing for them. The component ID is
  now parsed as `<host>/<owner>/<repository>[/<subpath>...]`, and the API base
  URL is derived from the host, so GHES components work too (#269).

- `secrets` policy (`no-hardcoded-secrets`): report each finding individually
  with its file, line, and rule instead of a single aggregate count, so PR
  comments and dashboards show exactly where each secret is (#268).

## [1.10.1] — 2026-07-21

### Changed

- `trivy` and `grype` collectors (`container-scan`): scan PR-pushed images too,
  not just merge/release images — dropped the `runs_on: [default-branch]` pin so
  the container-scan sub-collector defaults to `[prs, default-branch]`
  (skip-safe: a PR that pushed no image no-ops). Fleet-wide default for every
  hub importing `container-scan`; opt out per-import with
  `exclude: [container-scan]` (#265).

### Fixed

- `repo-boilerplate` policy: the CODEOWNERS sub-checks no longer hang on
  "No data at path …" when the `codeowners` collector reports no data for a
  component — they now resolve to a definitive result. A repo with no CODEOWNERS
  file fails the check rather than sitting pending (or erroring) indefinitely
  (#261).
- `repo-boilerplate` collector (`codeowners`): make the CODEOWNERS checks work
  in a monorepo. A CODEOWNERS file is only honored at the repository root, but
  in a monorepo each component runs from its own subdirectory, so the collector
  reported `exists: false` for every component. It now resolves the repository
  root and falls back to the global CODEOWNERS there, records a new
  `.ownership.codeowners.scope` field (`repo` vs `component`), and adds a
  `codeowners_scope` input (`auto` | `repo-root` | `component-dir`, default
  `auto`) to control the behavior (#260).

## [1.10.0] — 2026-07-21

### Added

- `backstage` collector + policy: referential-integrity checks `domain-exists`
  and `system-exists` — cross-reference the `spec.domain` / `spec.system` a
  repo's `catalog-info.yaml` declares against what actually exists in the
  Backstage catalog. Adds `backstage_url` / `namespace` inputs, a
  `BACKSTAGE_TOKEN` secret, and a normalized `.refs` view (#234).
- `trivy` and `grype` collectors: new `container-scan` sub-collector that scans
  a component's container image synchronously at publish time, via the new
  `after-json` collector hook (#254).
- `backstage-catalog-info` cataloger: nested subdomain/system domain paths —
  ports the nested-taxonomy resolver (added to the live-API `backstage`
  cataloger in #253) to the per-repo cataloger, so a `catalog-info.yaml` that
  declares its parent `Domain` / `System` chain in-file expands the component's
  domain to the full dotted path (`a.b.c`) instead of flattening into unrelated
  top-level domains (#259).

## [1.9.0] — 2026-07-17

### Added

- `github-org` and `backstage-catalog-info-monorepo` catalogers: opt repos
  into the catalog by GitHub topic. Both gain `allowed_topics` /
  `disallowed_topics` inputs (allow = repo must carry ≥1 listed topic;
  disallow = repo must carry none; block wins over allow). The
  `backstage-catalog-info-monorepo` cataloger additionally gains org
  auto-discovery: a new `orgs` input enumerates each org's repos and filters
  them by topic (honoring `include_archived`) before scanning, so a monorepo
  opts in via a repo topic instead of a hand-maintained `repos` list —
  explicitly-listed `repos` are always scanned. Additive; all new inputs
  default to empty/false (#250).
- `backstage` cataloger: opt-in `domain_hierarchy: nested` mode — resolves
  Backstage's nested taxonomy (`domain → subdomain → system → component`) via
  `spec.subdomainOf` into Lunar's dotted domain keys, instead of flattening a
  nested catalog into unrelated top-level domains (#253).

### Changed

- `gitops` policy: trim the `gitops-managed` check description from eight lines
  down to three (#255).

### Fixed

- `elixir` collector: build on the debian `lunar-scripts` base — the Alpine
  3.24 base aborts the Erlang build (#257).
- Pin `lunar-scripts` to 1.1.5, picking up the non-root collector fix (#258).

## [1.8.1] — 2026-07-10

### Fixed

- `checkov` collector: install a Rust toolchain so the `rustworkx` wheel builds
  on Alpine 3.24, fixing the `checkov` image build (#249).

## [1.8.0] — 2026-07-10

### Added

- ArgoCD GitOps guardrail set — three collectors and two policies over a
  normalized `.cd.gitops` view: `argocd` (beta) parses and
  kubeconform-validates argoproj CRDs (Application / ApplicationSet /
  AppProject); `argocd-deployment-tracking` (experimental) correlates each
  Application to the service it deploys and records that service's deployment
  posture out-of-band; `argocd-deployment-gate` (experimental) pulls the posture
  back for PR-time enforcement (mapping defaults to a cataloger-set meta
  annotation, with Backstage `catalog-info` opt-in). Adds the tool-agnostic
  `gitops` policy and the ArgoCD-specific `argocd` policy. Push and pull are
  mutually exclusive per service (#218).
- `kotlin` collector + policy: JVM-language detection and guardrails, filling
  the gap alongside the existing `java` and `scala` plugins (#242).
- `istio` collector + policy (experimental): parses Istio service-mesh
  configuration from the repo and applies guardrails over it (#245).
- `backstage-catalog-info-monorepo` cataloger: scans each configured repo for
  every `catalog-info.yaml` it contains — including files in subdirectories —
  creating one Lunar component per discovered file, keyed to the file's
  directory. Adds `catalog-info` ignore / exclude controls (#243).
- `backstage` cataloger: AWS SigV4 authentication with self-refreshing
  IAM-role credentials, for Backstage APIs fronted by AWS IAM auth (e.g. Amazon
  API Gateway) that reject Bearer tokens (#232).
- `backstage-catalog-info` cataloger: `meta_annotations` input — maps selected
  `catalog-info.yaml` annotations onto the Lunar component `meta` field.
  Defaults to `pagerduty.com/service-id=pagerduty/service-id`, so the
  `pagerduty` collector (and the `oncall` guardrails) discover a component's
  PagerDuty service straight from the annotation — no per-component config.
  Accepts multiple `<annotation>=<meta-key>` pairs; set empty to disable
  (#224).
- `backstage` policy: typed value constraints on `required-annotations` —
  assert an annotation's value is an integer in a range, matches a regex, or is
  drawn from a fixed set, not just that the key is present (#244).
- `trivy` and `grype` collectors: opt-in scan-history preservation — the
  `rescan` cron keeps prior results in `.sca.history` instead of overwriting
  the previous scan (#247).

### Changed

- `backstage` cataloger: switch to the `/catalog/entities/by-query` endpoint
  with cursor pagination, paging through large catalogs instead of issuing a
  single unpaginated request (#240).

### Fixed

- Collector inputs are now read via the `LUNAR_VAR_<NAME>` environment prefix.
  Six reads across five collectors used `LUNAR_INPUT_*` and were silently
  ignored — the script always fell back to its default (#248).

## [1.7.0] — 2026-07-07

### Added

- `trivy` and `grype` collectors: container-image vulnerability scanning. A new
  `container-rescan` sub-collector resolves the most recently shipped image
  (from a `docker push` / `--push` build recorded in
  `.containers.native.docker.cicd.cmds[]`), then pulls and scans it inside the
  collector's baked-DB image (daemonless), normalizing results to
  `.container_scan`. The `cicd` sub-collector now also routes a user's own
  `trivy image` / `grype <ref>` runs to `.container_scan` (while `fs`/`dir:`/
  `sbom:` scans still feed `.sca`). Feeds the existing `container-scan` policy,
  whose `max-severity` check now lists the offending packages/CVEs. Registry
  auth via the `REGISTRY_USERNAME`/`REGISTRY_PASSWORD` secrets (#221).
- `backstage` cataloger: new input to configure the Backstage API path prefix
  instead of hard-coding it (#236).

### Changed

- `trivy` collector: the scan sub-collectors now declare `size: large` (#235).

### Fixed

- Collector-backed presence checks (seven `ai/*` checks and two `git/*` checks)
  now PEND instead of FAIL while collection is still in flight. They gate on
  `node.exists()` (the pattern the `vcs` checks already use), so a missing value
  pends during the collection interim and only fails once collection has
  genuinely finished — eliminating the spurious FAILs that appeared on in-flight
  PRs and then flipped to pass/pending (#230).

## [1.6.0] — 2026-07-02

### Added

- `github-org` cataloger: new `default_domain` fallback input and GitHub
  Enterprise Server support (#220).
- `backstage-catalog-info` cataloger: new `augment-on-commit` sub-cataloger — a
  commit-triggered companion to the scheduled `augment`. Runs on the
  `component-repo` hook (`clone-code: true`) so it refreshes a component's
  owner/domain/tags the moment its repo is committed to, reading
  `catalog-info.yaml` from the checkout. Shares the parse/match/transform/write
  pipeline with `augment` via `helpers.sh`; enable either or both with `include`
  (#212).
- `backstage-catalog-info` cataloger: new `default_domain` input — assigns a
  fallback domain (written verbatim, with a matching stub `.domains` entry) to
  components whose `catalog-info.yaml` resolves to no domain via
  `domain_annotation`, `spec.domain`, or `spec.system`. Mirrors the existing
  `default_owner` fallback and never overrides a domain the file already
  provides (#223).
- `backstage` policy: new required/disallowed annotation checks and tag-pattern
  checks (#222).
- `pagerduty` collector: opt-in Backstage discovery of the service ID from
  `catalog-info.yaml` (#225).

### Changed

- `grype` collector: declares `size: large`; `db_auto_update` stays `false` by
  default until a size-aware Hub ships (#210, #229).
- Language policies now gate on project detection, while CI minimum-version
  checks stay ungated (#209).
- `sca` policy: the `max-severity` failure text drops the webhook mention and
  lists the offending findings (#214).
- Lint: block dev/personal `earthly/lunar-lib` image tags in manifests (#211).

### Fixed

- `github-org` cataloger: authenticate GitHub Enterprise Server hosts with
  `LUNAR_SECRET_GH_ENTERPRISE_TOKEN` (falling back to `LUNAR_SECRET_GH_TOKEN`)
  instead of always using `LUNAR_SECRET_GH_TOKEN`. Previously a distinct
  enterprise token set via `LUNAR_SECRET_GH_ENTERPRISE_TOKEN` was ignored and
  the github.com token was reused for GHE hosts. github.com behavior is
  unchanged (#226).
- `backstage-catalog-info` and `backstage` catalogers: an explicit empty
  `tag_prefix` now disables tag prefixing entirely, honoring the documented
  "empty string disables the prefix" behavior. Previously an empty value set in
  config was silently replaced with the `bs-` default — Bash `${VAR:-bs-}`
  treats empty and unset alike — so the prefix could not be turned off (#227).
- `github-org` cataloger: same `tag_prefix` fix as #227 — an explicit empty
  `tag_prefix` now disables the topic prefix instead of being silently replaced
  with the `gh-` default (`${VAR:-gh-}` treats empty and unset alike). The input
  is now documented as "empty string disables the prefix" (#228).
- `github` collector (branch-protection): don't fail open to `enabled=false` on
  transient API errors (#215).

## [1.5.0] — 2026-06-17

### Added

- `trivy` collector: new `rescan` cron sub-collector — re-runs the dependency
  (SCA) scan daily on each component's default branch and overwrites `.sca`, so
  the `sca` policy re-evaluates a previously-clean commit against CVEs published
  after it was first scanned. Reuses the existing `auto` scan (same `auto.sh`,
  same image) and stamps `.sca.source.integration` as `cron` (vs `code` for the
  on-push scan). Enabled by default; opt out with `exclude: [rescan]` (#205).
- `grype` collector: new `rescan` cron sub-collector — the same scheduled
  default-branch re-scan and `.sca` overwrite as `trivy`, symmetric behavior
  (#204).

## [1.4.0] — 2026-06-15

### Added

- New collector (beta): `grype` — scans repository dependencies for known CVEs
  using [Grype](https://github.com/anchore/grype), Anchore's open-source
  vulnerability scanner. Two sub-collectors mirror `trivy`: `auto` (code hook)
  scans the filesystem and normalizes findings into `.sca`; `cicd`
  (ci-after-command) records Grype invocations under `.sca.native.grype`. No
  secrets required, and it reuses the existing `sca` policy (added to its
  `requires:`) (#201).
- New probe bundle (beta): `python` — agent-time guardrails for Python
  projects, shipped as individually-includable sub-probes selected with
  `include:`. `disallowed-deps` hard-blocks dep / lock file edits that pin a
  package to a known-vulnerable version (seeded with widely-deployed Python
  CVEs incl. Starlette BadHost / CVE-2026-48710; consumers extend or replace
  the list); `ruff-lint` and `ruff-format` run Ruff over changed Python files
  (#187, #188).
- New probe bundle (beta): `docker` — `hadolint` sub-probe lints Dockerfiles
  during agent sessions and on PRs (#189).
- New probe bundle (beta): `shell` — `shellcheck` sub-probe, migrated from the
  standalone `shellcheck` probe into a per-language bundle (#198, #199).
- `terraform` policy: 29 AWS infrastructure security checks relevant to SOC 2,
  added across two batches as individually-includable sub-policies — EBS
  volume/snapshot encryption, CloudTrail multi-region + CloudWatch, GuardDuty,
  VPC flow logs, S3 public-access blocking and access logging, security-group
  ingress limits, EKS/RDS/ELB logging, HTTPS-only load balancers, WAF on public
  ALBs, and an account-level IAM password policy. Each reads
  `.iac.native.terraform.files` from the `terraform` collector (#192, #197).

### Changed

- `sca` policy: optional `alert_url` input — on a max-severity failure the
  policy additionally POSTs a best-effort CVE-findings webhook. Non-gating: the
  webhook outcome never changes the check result (#202).
- `snyk/cli` collector: normalize SCA results from `--json-file-output` into the
  shared `.sca` shape, matching `trivy` and `grype` (#194).

## [1.3.0] — 2026-06-03

### Added

- New catalogers (beta): `backstage` — syncs components and domains from a
  Backstage software catalog into Lunar, mapping entities with owner / domain /
  tags (#178); `backstage-catalog-info` — augments existing Lunar components
  with owner / domain / tag metadata read from each repo's `catalog-info.yaml`,
  fetched via the GitHub Contents API on a `component-cron` schedule, with a
  `domain_annotation` input for orgs that store the domain in a custom
  annotation rather than the canonical Backstage `spec.domain` field (#181).
- New probes (beta): `shellcheck` — the first lunar-lib probe (#167);
  `pr-title-ticket-ref` — flags PRs whose title doesn't reference a ticket
  (#184).
- `golang/golangci-lint-ci` sub-collector — detects user-invoked `golangci-lint`
  runs in CI (#183).
- `repo-boilerplate`: `changelog-exists` check (#180).
- This CHANGELOG file (#185). Going forward, every PR should add an entry under
  `[Unreleased]` for any user-visible change (new collector / policy / cataloger
  / probe, manifest schema change, breaking rename, new starter-pack, etc.).
  Internal refactors and docs-only changes don't need an entry.

### Changed

- `github` collector: detect ruleset-based branch protection in addition to the
  classic branch-protection API (#179).
- `trivy` collector: preserve the raw Trivy JSON under
  `.sca.native.trivy.results` (#190).
- `policies/ticket`: drop Jira-specific wording from `ticket-present` (#177).

### Fixed

- `repo-boilerplate`: fix the `assert_true(.exists)` anti-pattern (#186).

## [1.2.0] — 2026-05-15

### Added

- New collectors (beta): `backstage` (#128), `datadog` (#142), `dependabot`
  (#129), `elixir` (#141), `endoflife` (#155), `git` (#160), `grafana` (#137),
  `helm` (#127), `opsgenie` (#158), `pagerduty` (#126), `renovate` (#129),
  `scala` (#154), `sonarqube` (#138).
- `k8s/cicd` sub-collector — traces `kubectl` invocations in CI to detect
  cluster targets (#135).
- `terraform/cicd` sub-collector — traces `terraform` invocations in CI (#133).
- New policies (beta): `k8s/host-namespace` with four sub-policies
  (`host-users`, `host-network`, `host-pid`, `host-ipc`) (#168);
  `k8s/min-kubectl-version` (#139); `code-quality/sonarqube` (#138);
  `catalog` Backstage completeness/ownership (#128); `dep-automation`
  (#129); `observability/slo-defined` (#142, #137); `oncall`
  (PagerDuty + OpsGenie) (#126, #158).
- `cronos-runner-required` check (#157).
- `cronos-cheat-sheet` agent-session-start hook (#146).
- `screenshot-guard` hook (force screenshots through `bender-screenshot`) (#153).
- `gh-issue-guard` + `gh-comments-guard` hooks (route ticket/comment ops
  through sanctioned path) (#152).

### Changed

- README rewrite — branded overview with starter-pack onboarding (#145).
- AI context split by phase so phase guidance routes to focused docs (#159).
- AI context documents component-cron hook + Component-JSON-heuristics
  pattern (#171).
- Ported `.lunar/checks.yml` to `.lunar/probes.yml` (lunar-probe dogfood) (#161).
- Lint validators run per file edit instead of via session-end target (#156);
  lint moved to stop-phase, once per session instead of per file (#130).
- Unified `.lunar/checks.yml` hook vocabulary; added `agent-before-command`,
  `agent-before-tool-call`, `agent-after-file-edit-nudge` (#140).
- PR workflow migrated from Claude to CodeRabbit (#162); manual CodeRabbit
  summon removed from docs (#173).
- Starter-pack refs pinned to `@v1.1.0` (#134).

### Removed

- Stale `readme` + `codeowners` plugins (superseded by `repo-boilerplate`) (#143).
- `AI-Use Policy` (fully replaced by `ai` policy) (#131).

### Fixed

- `secrets` collector: default `max_issues_threshold` to 10 (#144).
- SVG icons flattened — fixes washed-out transparency on main shapes (#147).
- `java/cicd.sh` no longer depends on `sed` (#136).
- Docs: replace stale `sync-manifest` name with `Sync Lunar Config` (#169, #170).

## [1.1.0] — 2026-04-15

### Added

- New collectors: `repo-boilerplate` (#109), `html` (#106), `c-cpp` (#102),
  `ruby` (#112), `github-actions` (#101), `gitleaks` / `secrets` (#97),
  `api-docs` (#99), `checkov` IaC security scanning (#111),
  `linear` ticket (#72), `.NET/C#` (#94).
- `docker/hadolint` sub-collector (#114).
- `shell` collector + policy (ShellCheck + bash detection) (#115).
- GitHub Actions security policy — collector enhancement + 6 policy
  checks (#116).
- AI guardrails: tool-specific collectors + unified `ai` namespace (#105).
- Five starter packs: Security, Code Quality, Cloud Native, Baseline,
  AI Native (#121).
- `.lunar/checks.yml` for agent guardrails; playbook rewrite (#122).
- Screenshot quality reminder in `.lunar/checks.yml` (#124).
- AI release guide (#125).
- Earthfile wiring lint check for missing collector entries (#103).

### Changed

- Adopt nested tool-scoped `cicd` convention across language
  collectors (#98).
- Skip language policies when only CI data exists (no code collector) (#85).
- Generalized reviewer-assignment guidance in plugin playbook (#100).
- Refined integration-testing workflow in playbook (#110).
- Replace CodeRabbit with Claude Code Review (#117) — note: reverted
  to CodeRabbit in v1.2.0 (#162).

### Removed

- Loose source-file fallback from language project detection (#92).
- Local CI-simulation testing from playbook — real cronos testing
  required (#104).

### Fixed

- GitHub collector early-exit logging + VCS policy pending state (#123).
- Cronos cleanup workflow: new vs existing collectors (#120).
- Pinned SHA for `hmarr/auto-approve-action`.

## [1.0.5] — 2026-03-25

### Added

- `codeql` collector (#91).

### Fixed

- `syft` CI collector never collecting SBOM files (#93).
- Rust collector bash bugs causing failures across all components (#90).

## [1.0.4] — 2026-03-21

### Added

- Rust/Cargo license detection in Syft SBOM collector (#88).
- Release instructions (`RELEASE.md`).
- `sbom` accepts JSON array strings for `disallowed_licenses` and
  `disallowed_packages` (#82).

### Changed

- Bump `lunar-policy` to 0.2.3 in all policies (#86).

### Fixed

- Collectors querying removed `components_latest2` view (#89).
- Release script on macOS: `find -exec` can't call shell functions.

## [0.1.0] — 2026-03-19

Initial tagged release. Earlier history captured in
[git log](https://github.com/earthly/lunar-lib/commits/v0.1.0).

[Unreleased]: https://github.com/earthly/lunar-lib/compare/v1.14.2...HEAD
[1.14.2]: https://github.com/earthly/lunar-lib/compare/v1.14.1...v1.14.2
[1.14.1]: https://github.com/earthly/lunar-lib/compare/v1.14.0...v1.14.1
[1.14.0]: https://github.com/earthly/lunar-lib/compare/v1.13.0...v1.14.0
[1.13.0]: https://github.com/earthly/lunar-lib/compare/v1.12.2...v1.13.0
[1.12.2]: https://github.com/earthly/lunar-lib/compare/v1.12.1...v1.12.2
[1.12.1]: https://github.com/earthly/lunar-lib/compare/v1.12.0...v1.12.1
[1.12.0]: https://github.com/earthly/lunar-lib/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/earthly/lunar-lib/compare/v1.10.1...v1.11.0
[1.10.1]: https://github.com/earthly/lunar-lib/compare/v1.10.0...v1.10.1
[1.10.0]: https://github.com/earthly/lunar-lib/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/earthly/lunar-lib/compare/v1.8.1...v1.9.0
[1.8.1]: https://github.com/earthly/lunar-lib/compare/v1.8.0...v1.8.1
[1.8.0]: https://github.com/earthly/lunar-lib/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/earthly/lunar-lib/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/earthly/lunar-lib/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/earthly/lunar-lib/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/earthly/lunar-lib/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/earthly/lunar-lib/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/earthly/lunar-lib/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/earthly/lunar-lib/compare/v1.0.5...v1.1.0
[1.0.5]: https://github.com/earthly/lunar-lib/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/earthly/lunar-lib/compare/v0.1.0...v1.0.4
[0.1.0]: https://github.com/earthly/lunar-lib/releases/tag/v0.1.0
