# AI Context about Lunar collectors and policies (guardrails)

This directory contains reference documentation for AI agents working with the Lunar platform.

---

## Mandatory Checks (All Workers)

**These rules are non-negotiable. Follow them every time you work in this repo.**

### Before Committing

1. **Run the linter if you changed spec files**: If you modified any files in `collectors/` or `policies/` (YAML manifests, READMEs, SVGs, requirements.txt), run `earthly +lint` and fix ALL errors before committing. You can skip it for changes that don't touch those directories.
2. **Validate YAML manifests**: Ensure all `requires` references point to collectors/policies that actually exist. The linter checks this.
3. **Stage only relevant files**: Use `git add collectors/<name>/` or `git add policies/<name>/` — never `git add .` or `git add -A`.

### After Pushing

1. **Check CI status**: Run `gh pr checks <PR>` and verify all checks pass.
2. **Fix failures immediately**: If CI fails, read the logs (`gh run view <run-id> --log-failed`), fix the issue, and push again. Do not leave a PR with failing CI.

### SVG Icon Guidelines

When creating or editing SVG icons for collectors, policies, or catalogers:

1. **Use `fill="black"`** — the website converts black to white at render time. Black is visible in GitHub PR diffs; white is invisible on GitHub's white background.
2. **Source from [simple-icons](https://github.com/simple-icons/simple-icons)** when a standard icon exists. Strip `<title>` tags and `role="img"` attributes.
3. **No solid background rectangles** — use transparent backgrounds only.
4. **No colored fills** — only `black`, `white` (with `fill-opacity`), `none`, or `currentColor`. RGB colors get flattened.
5. **Validate before committing**: `earthly +lint` runs `validate_svg_grayscale.py` which enforces these rules.
6. **Full guidelines**: See `LUNAR-PLUGIN-PLAYBOOK-AI.md` (SVG section) for the complete reference.

### Phase Awareness

- **Spec-only phase**: Only create/edit YAML manifests, READMEs, SVGs, and documentation. No `.sh` or `.py` implementation files.
- **Implementation phase**: Write the code. Test locally with `lunar collector dev` / `lunar policy dev` before pushing.
- Check the PR title and conversation context for which phase you're in. `[Spec Only]` in the title = spec phase.

---

## Reference Documentation

* [about-lunar.md](ai-context/about-lunar.md): **Start here.** High-level overview of the Lunar platform, the problem it solves, and key concepts from a user perspective.
* [core-concepts.md](ai-context/core-concepts.md): **Then read this.** Comprehensive explanation of Lunar's architecture, key entities, execution flow, and how collectors/policies interact via the Component JSON.
* [collector-reference.md](ai-context/collector-reference.md): Complete guide to writing collectors—hooks, environment variables, the `lunar collect` command, patterns, and best practices.
* [cataloger-reference.md](ai-context/cataloger-reference.md): Complete guide to writing catalogers—syncing catalog data from external systems, the `lunar catalog` command, patterns, and best practices.
* [policy-reference.md](ai-context/policy-reference.md): Complete guide to writing policies—the Check class, assertions, handling missing data, patterns, and testing.

## Component JSON Schema

The Component JSON schema documentation lives in [component-json/](ai-context/component-json/):

* [conventions.md](ai-context/component-json/conventions.md): **The schema contract.** Design principles, source metadata patterns, presence detection, PR-specific data, native data, and language-specific patterns.
* [structure.md](ai-context/component-json/structure.md): **The category reference.** Quick reference table of all paths, links to individual category docs (`.repo`, `.sca`, `.k8s`, etc.), naming conventions, and schema extension guidelines.

The `structure.md` file links to individual category files (`cat-repo.md`, `cat-sca.md`, etc.) for detailed examples and key policy paths.

## Plugin Templates

* [collector-README-template.md](ai-context/collector-README-template.md): Standard README.md template for collector plugins.
* [cataloger-README-template.md](ai-context/cataloger-README-template.md): Standard README.md template for cataloger plugins.
* [policy-README-template.md](ai-context/policy-README-template.md): Standard README.md template for policy plugins.

## Implementation Guides

* **[LUNAR-PLUGIN-PLAYBOOK-AI.md](.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md): Read this first for new PRs.** End-to-end playbook for AI agents creating new collectors and policies — covers the full PR lifecycle (spec → go-ahead → implementation → approval → merge), testing requirements, common mistakes, and reviewer workflow.
* [guardrail-specs](ai-context/guardrail-specs): Guardrail specifications for the AI to implement. This contains the specifications for each guardrail, together with suggested approach to implement it.
* [strategies.md](ai-context/strategies.md): Common strategies to be used for implementing the guardrails (policy and collector plugins).
