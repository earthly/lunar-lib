# Contributing to lunar-lib

Thanks for taking the time to contribute. This repo holds the official collector, policy, and cataloger plugins for [Earthly Lunar](https://earthly.dev/lunar) — it grows continuously, and most contributions take the form of **new plugins** or **improvements to existing ones**.

## Before You Start

- New to Lunar? Read [earthly.dev/lunar](https://earthly.dev/lunar) first.
- **Using an AI agent** (Claude Code, Cursor, Codex, …) to write your plugin? Point it at [`AGENTS.md`](./AGENTS.md) — that's the AI-first entry point, and it links every authoring guide, schema reference, and convention doc the agent will need. Writing by hand? It's still the fastest way to find those same docs yourself.
- Browse a few existing entries in [`collectors/`](./collectors) and [`policies/`](./policies) that are similar to what you want to build — consistency with existing patterns is the #1 thing reviewers look for.

## The Workflow: Spec-First

Plugins ship on a two-phase workflow so reviewers can catch design issues before implementation time is spent.

1. **Open a `[Spec Only]` draft PR.** Include the plugin manifest, README, example Component JSON, and any policy requirements — but **no implementation code** (no scripts in `collectors/<name>/`, no `*.py` in `policies/<name>/`).
2. **Get reviewer go-ahead on the spec.** A secondary reviewer's approval on the spec PR is the signal to start implementing. Do **not** open a separate PR for the implementation — it goes on the same branch.
3. **Implement on the same PR.** Remove the `[Spec Only]` marker from the title and push the implementation.
4. **Post integration-test evidence.** For CI-hook collectors, run a full cronos round-trip and attach the Component JSON + screenshots. Local `lunar collector dev` runs alone aren't enough.
5. **Merge.** Squash-merge once all assigned reviewers approve and CI is green.

The end-to-end playbook — including testing requirements, common mistakes, and phase transitions — lives in [`.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md`](./.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md).

## PR Basics

- **Branch prefix:** any descriptive name is fine; `bender/` is reserved for the automated agent.
- **PRs open as drafts** and are marked ready for review once the spec (or implementation) is complete.
- **One plugin per PR.** Bundling multiple plugins makes review slow and risky.
- **Keep the README template.** Plugin READMEs follow the templates in `ai-context/` (linked from `AGENTS.md`) — reviewers rely on consistent structure.

## Starter Packs

If you're proposing changes to [`starter-packs/`](./starter-packs/), keep in mind these are opinionated, curated bundles. Additions should raise the bar for the target tier (zero config / light config / specialized) without adding noise for users who adopt the pack wholesale.

## Questions

Open a draft PR with a `[RFC]` marker in the title, or reach out in the existing PR thread most closely related to your idea. We'd rather talk early than reject late.

## License

By contributing, you agree that your contributions will be licensed under the [Mozilla Public License 2.0](./LICENSE).
