<div align="center">

# 🌙 lunar-lib

**The official plugin library for [Earthly Lunar](https://earthly.dev/lunar) — a guardrails engine for the AI era.**

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](./LICENSE)
[![Lunar Platform](https://img.shields.io/badge/platform-Lunar-7c3aed)](https://earthly.dev/lunar)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-blue.svg)](#contributing)

</div>

---

## What is lunar-lib?

Lunar enforces engineering standards across every repo, every PR, and every AI coding session in your organization — without the per-repo setup, Slack announcements, or backlog tickets that usually come with it.

**lunar-lib is the open-source plugin library that powers it.** It's a curated, continuously-growing catalog of:

- **Collectors** — gather metadata from your codebase (languages, dependencies, CI configs, IaC, security scans, AI tool usage, etc.)
- **Policies** — evaluate that metadata against engineering standards and report findings as PR comments, gates, or scores
- **Catalogers** — sync component and ownership data from external systems (GitHub orgs, service catalogs, etc.)
- **Starter packs** — opinionated, ready-to-import bundles of the above for common scenarios

Browse [`collectors/`](./collectors), [`policies/`](./policies), and [`catalogers/`](./catalogers) for the full, always-current list.

> New to Lunar itself? Start with [**ai-context/about-lunar.md**](./ai-context/about-lunar.md) for the platform overview, then [**core-concepts.md**](./ai-context/core-concepts.md) for how collectors, policies, and the Component JSON fit together.

---

## Where to Start

Don't pick plugins one at a time. Start with a **starter pack** — a curated `lunar-config.yml` that's wired up and ready to drop into your repo.

| Tier | What you get | Setup |
|------|--------------|-------|
| **[Starter](./starter-packs/starter/)** | Zero config, zero secrets. Themed packs for Security, Code Quality, Cloud Native, AI Native, plus a Baseline. | Copy → done. |
| **[Starter Plus](./starter-packs/starter-plus/)** | Adds vendor integrations (Snyk, SonarQube, Jira, PagerDuty, …). | One token or URL per integration. |
| **[Advanced](./starter-packs/advanced/)** | Specialized workflows (custom AST rules, OTel, GitOps, AI governance). | Real configuration required. |

**Recommended path for new users:**

1. Read [`starter-packs/README.md`](./starter-packs/README.md) for the full tier breakdown.
2. Pick a Starter pack (try [**Baseline**](./starter-packs/starter/baseline/) if you can't decide).
3. Copy its `lunar-config.yml` into your repo root.
4. Tune enforcement levels (`score` → `report-pr` → `block-pr`) as your team gets comfortable.

---

## Repository Layout

```
lunar-lib/
├── ai-context/         📚 Platform docs, schemas, plugin authoring guides
├── starter-packs/      🚀 Curated, ready-to-use lunar-config.yml bundles
├── collectors/         🔍 Plugins that gather metadata into the Component JSON
├── policies/           ✅ Plugins that evaluate that metadata against standards
├── catalogers/         🗂️  Plugins that sync external component/ownership data
└── .ai-implementation/ 🤖 Playbooks for AI agents contributing new plugins
```

---

## Documentation

| Topic | Where to look |
|-------|---------------|
| What Lunar is and the problem it solves | [`ai-context/about-lunar.md`](./ai-context/about-lunar.md) |
| Architecture, Component JSON, execution flow | [`ai-context/core-concepts.md`](./ai-context/core-concepts.md) |
| Writing a collector | [`ai-context/collector-reference.md`](./ai-context/collector-reference.md) |
| Writing a policy | [`ai-context/policy-reference.md`](./ai-context/policy-reference.md) |
| Writing a cataloger | [`ai-context/cataloger-reference.md`](./ai-context/cataloger-reference.md) |
| Component JSON schema conventions | [`ai-context/component-json/`](./ai-context/component-json/) |
| End-to-end PR playbook (humans & agents) | [`.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md`](./.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md) |

---

## Contributing

Plugins in `lunar-lib` are reviewed and shipped continuously. The workflow is **spec-first**:

1. **Open a `[Spec Only]` draft PR** with manifests, README, and examples — no implementation code yet.
2. **Get reviewer go-ahead** on the spec.
3. **Implement on the same PR.**
4. **Merge** once approvals land.

Full details, conventions, and reviewer expectations live in [`.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md`](./.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md). AI agents authoring plugins should read [`AGENTS.md`](./AGENTS.md) first.

---

## License

[Mozilla Public License 2.0](./LICENSE) — see file for details.

<div align="center">

Built and maintained by the team behind [Earthly](https://earthly.dev).

</div>
