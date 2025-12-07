# AI Context about Lunar collectors and policies (guardrails)

This directory contains reference documentation for AI agents working with the Lunar platform.

## Reference Documentation

* [about-lunar.md](about-lunar.md): **Start here.** High-level overview of the Lunar platform, the problem it solves, and key concepts from a user perspective.
* [core-concepts.md](core-concepts.md): **Then read this.** Comprehensive explanation of Lunar's architecture, key entities, execution flow, and how collectors/policies interact via the Component JSON.
* [collector-reference.md](collector-reference.md): Complete guide to writing collectors—hooks, environment variables, the `lunar collect` command, patterns, and best practices.
* [policy-reference.md](policy-reference.md): Complete guide to writing policies—the Check class, assertions, handling missing data, patterns, and testing.
* [component-json-conventions.md](component-json-conventions.md): **The schema contract.** Design principles and conventions for Component JSON—source metadata, presence detection, PR-specific data, native data, and language-specific patterns.
* [component-json-structure.md](component-json-structure.md): **The category reference.** Standard structure for each top-level category (`.repo`, `.sca`, `.k8s`, etc.) with examples and key policy paths.

## Plugin Templates

* [collector-README-template.md](collector-README-template.md): Standard README.md template for collector plugins.
* [policy-README-template.md](policy-README-template.md): Standard README.md template for policy plugins.

## Implementation Guides

* [guardrails-inspiration.md](guardrails-inspiration.md): Guardrails (policy and collector plugins) for the AI to implement. This contains a short description of each guardrail, together with suggested approach to implement it.
* [../guardrail-specs](../guardrail-specs): Guardrail specifications for the AI to implement. This contains the specifications for each guardrail, together with suggested approach to implement it.
* [strategies.md](strategies.md): Common strategies to be used for implementing the guardrails (policy and collector plugins).
