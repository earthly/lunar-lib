# Code Quality & Standards Starter Pack

For teams focused on testing, linting, code ownership, and repo hygiene. This is the most comprehensive pack — it includes language-specific guardrails for every detected language.

## What's Included

### Collectors
| Collector | Purpose |
|-----------|---------|
| All language collectors | Auto-detect languages, skip if absent |
| `readme` | README analysis |
| `codeowners` | CODEOWNERS file parsing |
| `repo-boilerplate` | Standard repo files detection |
| `github` | Repo settings |
| `codecov` | Coverage data (skips if not configured) |

### Policies

**Repo Standards**
| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `repo-boilerplate` | `readme-exists`, `codeowners-exists`, `gitignore-exists`, `license-exists` | report-pr | Essential repo files should exist |
| `repo-boilerplate` | `readme-min-line-count`, `editorconfig-exists`, `security-exists`, `contributing-exists` | score | Nice-to-have standards |
| `codeowners` | `exists`, `valid` | report-pr | Ownership should be defined |
| `codeowners` | `catchall`, `min-owners` | score | Track ownership maturity |

**Testing & Linting**
| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `testing` | `executed`, `passing` | report-pr | Tests should run and pass |
| `testing` | `coverage-collected`, `coverage-reported` | score | Track coverage adoption |
| `linter` | `ran` | score | Track linter adoption |
| `dependencies` | `min-versions` | report-pr | Dependencies should be recent |

**Language Guardrails (all at score)**
| Policy | Key Checks |
|--------|------------|
| `golang` | `go-mod-exists`, `go-sum-exists`, `min-go-version`, `tests-recursive` |
| `java` | `build-tool-wrapper-exists`, `min-java-version`, `tests-all-modules` |
| `nodejs` | `lockfile-exists`, `typescript-configured`, `engines-pinned`, `min-node-version` |
| `python` | `lockfile-exists`, `linter-configured`, `min-python-version` |
| `rust` | `cargo-toml-exists`, `cargo-lock-exists`, `min-rust-edition`, `clippy-clean` |
| `php` | `composer-json-exists`, `composer-lock-exists`, `phpunit-configured`, `min-version` |
| `cpp` | `build-system-exists`, `min-cpp-standard`, `cppcheck-clean` |
| `dotnet` | `project-file-exists`, `target-framework-set`, `dependencies-locked`, `test-project-exists` |
| `html` | `htmlhint-clean`, `stylelint-clean` |

## Enforcement Philosophy

- **report-pr**: Repo essentials (README, CODEOWNERS, license) and test execution — visible on every PR
- **score**: Language-specific checks, coverage tracking, linting — health dashboard visibility without PR noise while your team adopts standards

## Tightening Over Time

As your team matures, consider promoting:
1. `testing.executed` + `testing.passing` → `block-pr` (once all repos have tests)
2. Language lockfile checks → `report-pr` (once dependency hygiene is established)
3. `codeowners.catchall` → `report-pr` (once all repos have catch-all ownership)
4. `linter.ran` → `report-pr` (once all repos have linters configured)
