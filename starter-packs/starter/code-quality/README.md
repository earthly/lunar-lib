# Code Quality & Standards Starter Pack

For teams focused on testing, linting, code ownership, and repo hygiene. This is the most comprehensive pack — it includes language-specific guardrails for every detected language. Everything runs at `score` level for a frictionless day-1 experience.

## What's Included

### Collectors
| Collector | Purpose |
|-----------|---------|
| All language collectors | Only trigger when the language is detected |
| `codeowners` | CODEOWNERS file parsing |
| `repo-boilerplate` | Standard repo files detection |
| `github` | Repo settings |
| `codecov` | Coverage data (skips if not configured) |

### Policies

**Repo Standards (all at score)**
| Policy | Checks |
|--------|--------|
| `repo-boilerplate` | `readme-exists`, `codeowners-exists`, `gitignore-exists`, `license-exists`, `readme-min-line-count`, `editorconfig-exists`, `security-exists`, `contributing-exists` |
| `codeowners` | `exists`, `valid`, `catchall`, `min-owners` |
| `vcs` | `branch-protection-enabled`, `require-pull-request` |

**Testing & Linting (all at score)**
| Policy | Checks |
|--------|--------|
| `testing` | `executed`, `passing`, `coverage-collected`, `coverage-reported` |
| `linter` | `ran` |

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
| `shell` | `shellcheck-clean` |
| `ruby` | `gemfile-exists`, `lockfile-exists`, `ruby-version-set`, `bundler-audit-clean` |
| `html` | `htmlhint-clean`, `stylelint-clean` |

## Enforcement Philosophy

- **Everything at score** — gives your team a comprehensive quality dashboard without any PR friction on day 1

## Tightening Over Time

As your team matures, consider promoting:
1. `testing.executed` + `testing.passing` → `report-pr` (once all repos have tests)
2. `repo-boilerplate.readme-exists` → `report-pr` (once READMEs are standard)
3. Language lockfile checks → `report-pr` (once dependency hygiene is established)
4. `linter.ran` → `report-pr` (once all repos have linters configured)
