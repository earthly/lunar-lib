# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- This file. Going forward, every PR should add an entry under `[Unreleased]`
  for any user-visible change (new collector / policy / cataloger / probe,
  manifest schema change, breaking rename, new starter-pack, etc.). Internal
  refactors and docs-only changes don't need an entry.

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

[Unreleased]: https://github.com/earthly/lunar-lib/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/earthly/lunar-lib/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/earthly/lunar-lib/compare/v1.0.5...v1.1.0
[1.0.5]: https://github.com/earthly/lunar-lib/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/earthly/lunar-lib/compare/v0.1.0...v1.0.4
[0.1.0]: https://github.com/earthly/lunar-lib/releases/tag/v0.1.0
