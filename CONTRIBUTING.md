# Contributing to lunar-lib

Thanks for taking the time to contribute. This repo holds the official collector, policy, and cataloger plugins for [Earthly Lunar](https://earthly.dev/lunar) — it grows continuously, and most contributions take the form of **new plugins** or **improvements to existing ones**.

## Before You Start

- New to Lunar? Read [earthly.dev/lunar](https://earthly.dev/lunar) first.
- **Using an AI agent** (Claude Code, Cursor, Codex, …) to write your plugin? Point it at [`AGENTS.md`](./AGENTS.md) — that's the AI-first entry point. It links every authoring guide, schema reference, convention doc, and the recommended contribution workflow your agent should discover and follow on its own. Writing by hand? Same doc is still the fastest way to find those references yourself.
- Browse a few existing entries in [`collectors/`](./collectors) and [`policies/`](./policies) that are similar to what you want to build — consistency with existing patterns is the #1 thing reviewers look for.

## Recommended Workflow: Spec First

For non-trivial plugins, we've found a two-phase workflow saves everyone time. It's a suggestion, not a hard requirement:

1. **Open a draft PR with just the spec** — the plugin manifest, README, example Component JSON, and (for policies) `requirements.txt`. Hold off on implementation code.
2. **Get reviewer feedback on the spec** before investing implementation time. Design issues are cheaper to fix when there's no code to rewrite.
3. **Add the implementation on the same branch** once the spec looks good, and mark the PR ready for review.

Small fixes, doc updates, and tweaks to existing plugins don't need the spec-first dance — just open a PR.

## PR Basics

- **PRs open as drafts** and are marked ready for review once they're complete.
- **One plugin per PR.** Bundling multiple plugins makes review slow and risky.
- **Keep the README template.** Plugin READMEs follow the templates linked from [`AGENTS.md`](./AGENTS.md) — reviewers rely on consistent structure.
- **Include test evidence for collectors.** For CI-hook collectors in particular, show the collector actually produced the expected Component JSON on a representative repo.

## Starter Packs

If you're proposing changes to [`starter-packs/`](./starter-packs/), keep in mind these are opinionated, curated bundles. Additions should raise the bar for the target tier (zero config / light config / specialized) without adding noise for users who adopt the pack wholesale.

## Questions

Open a draft PR with a `[RFC]` marker in the title, or reach out in the existing PR thread most closely related to your idea. We'd rather talk early than reject late.

## License

By contributing, you agree that your contributions will be licensed under the [Mozilla Public License 2.0](./LICENSE).
