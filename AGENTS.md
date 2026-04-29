# AI Context about Lunar collectors and policies (guardrails)

This directory contains reference documentation for AI agents working with the Lunar platform.

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

* **[growth-roadmap.md](.ai-implementation/growth-roadmap.md): Prioritized implementation roadmap.** When asked to work on the next P1 (or any priority), look here for the ordered list of collectors and policies to build next.
* **[LUNAR-PLUGIN-PLAYBOOK-AI.md](.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md): Read this first for new PRs.** Overview of the PR lifecycle (spec → go-ahead → implementation → approval → merge) plus cross-cutting common mistakes and conventions. The phase-by-phase deep content lives in [`.ai-implementation/phases/`](.ai-implementation/phases/) — one doc per phase (`spec.md`, `implementation.md`, `impl-review.md`, `merge.md`) so you can read just the doc that matches your current phase. The `agent-session-start` hook in [`.lunar/checks.yml`](.lunar/checks.yml) auto-routes you to the right phase doc each session.
* [guardrail-specs](ai-context/guardrail-specs): Guardrail specifications for the AI to implement. This contains the specifications for each guardrail, together with suggested approach to implement it.
* [strategies.md](ai-context/strategies.md): Common strategies to be used for implementing the guardrails (policy and collector plugins).
