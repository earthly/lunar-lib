# AI Context about Lunar collectors and policies (guardrails)

This directory contains reference documentation for AI agents working with the Lunar platform.

## Reference Documentation

* [about-lunar.md](about-lunar.md): **Start here.** High-level overview of the Lunar platform, the problem it solves, and key concepts from a user perspective.
* [core-concepts.md](core-concepts.md): **Then read this.** Comprehensive explanation of Lunar's architecture, key entities, execution flow, and how collectors/policies interact via the Component JSON.
* [collector-reference.md](collector-reference.md): Complete guide to writing collectors—hooks, environment variables, the `lunar collect` command, patterns, and best practices.
* [policy-reference.md](policy-reference.md): Complete guide to writing policies—the Check class, assertions, handling missing data, patterns, and testing.
* [component-json-conventions.md](component-json-conventions.md): **The schema contract.** Standard structure and naming conventions for Component JSON across all categories.

## Plugin Templates

* [collector-README-template.md](collector-README-template.md): Standard README.md template for collector plugins.
* [policy-README-template.md](policy-README-template.md): Standard README.md template for policy plugins.

## Implementation Guides

* [guardrails.md](guardrails.md): Guardrails (policy and collector plugins) for the AI to implement. This contains a short description of each guardrail, together with suggested approach to implement it.
* [strategies.md](strategies.md): Common strategies to be used for implementing the guardrails (policy and collector plugins).
