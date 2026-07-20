# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed

- `backstage` cataloger: switch to the `/catalog/entities/by-query` endpoint
  with cursor pagination, paging through large catalogs instead of issuing a
  single unpaginated request (#240).
- `repo-boilerplate` collector (`codeowners`): make the CODEOWNERS checks work
  in a monorepo. A CODEOWNERS file is only honored at the repository root, but
  in a monorepo each component runs from its own subdirectory, so the check
  previously reported `exists: false` for every component. It now resolves the
  repository root and falls back to the global CODEOWNERS there, records a new
  `.ownership.codeowners.scope` field (`repo` vs `component`), and exposes a
  `codeowners_scope` input (`auto` | `repo-root` | `component-dir`, default
  `auto`) to control the behavior (ENG-1248).

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
- `backstage-catalog-info` cataloger: new `meta_annotations` input — maps
  selected `catalog-info.yaml` annotations onto the Lunar component `meta`
  field. Defaults to `pagerduty.com/service-id=pagerduty/service-id`, so the
  `pagerduty` collector (and the `oncall` guardrails) discover a component's
  PagerDuty service straight from the annotation PagerDuty's Backstage
  integration guide recommends — no per-component config. Accepts multiple
  `<annotation>=<meta-key>` pairs for other collectors; set empty to disable.
  (#224)
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

[Unreleased]: https://github.com/earthly/lunar-lib/compare/v1.7.0...HEAD
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
