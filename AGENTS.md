# AI Context about Lunar collectors and policies (guardrails)

This directory contains reference documentation for AI agents working with the Lunar platform.

## Reference Documentation

* [about-lunar.md](ai-context/about-lunar.md): **Start here.** High-level overview of the Lunar platform, the problem it solves, and key concepts from a user perspective.
* [core-concepts.md](ai-context/core-concepts.md): **Then read this.** Comprehensive explanation of Lunar's architecture, key entities, execution flow, and how collectors/policies interact via the Component JSON.
* [collector-reference.md](ai-context/collector-reference.md): Complete guide to writing collectors—hooks, environment variables, the `lunar collect` command, patterns, and best practices.
* [policy-reference.md](ai-context/policy-reference.md): Complete guide to writing policies—the Check class, assertions, handling missing data, patterns, and testing.
* [component-json-conventions.md](ai-context/component-json-conventions.md): **The schema contract.** Design principles and conventions for Component JSON—source metadata, presence detection, PR-specific data, native data, and language-specific patterns.
* [component-json-structure.md](ai-context/component-json-structure.md): **The category reference.** Standard structure for each top-level category (`.repo`, `.sca`, `.k8s`, etc.) with examples and key policy paths.

## Plugin Templates

* [collector-README-template.md](ai-context/collector-README-template.md): Standard README.md template for collector plugins.
* [policy-README-template.md](ai-context/policy-README-template.md): Standard README.md template for policy plugins.

## Implementation Guides

* [guardrail-specs](ai-context/guardrail-specs): Guardrail specifications for the AI to implement. This contains the specifications for each guardrail, together with suggested approach to implement it.
* [strategies.md](ai-context/strategies.md): Common strategies to be used for implementing the guardrails (policy and collector plugins).
