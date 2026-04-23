<div align="center">

<a href="https://earthly.dev/lunar"><img src="./.github/lunar-logo.png" alt="Earthly Lunar" width="420" /></a>

# lunar-lib

**The official plugin library for [Earthly Lunar](https://earthly.dev/lunar) — a guardrails engine for the AI era.**

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](./LICENSE)
[![Lunar Platform](https://img.shields.io/badge/platform-Lunar-7c3aed)](https://earthly.dev/lunar)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-blue.svg)](./CONTRIBUTING.md)

</div>

---

## What is lunar-lib?

Lunar enforces engineering standards across every repo, every PR, and every AI coding session in your organization — without the per-repo setup, Slack announcements, or backlog tickets that usually come with it.

**lunar-lib is the open-source plugin library that powers it.** It's a curated, continuously-growing catalog of:

- **Collectors** — gather metadata from your codebase (languages, dependencies, CI configs, IaC, security scans, AI tool usage, etc.)
- **Policies** — evaluate that metadata against engineering standards and report findings as PR comments, gates, or scores
- **Catalogers** — sync component and ownership data from external systems (GitHub orgs, service catalogs, etc.)
- **Starter packs** — opinionated, ready-to-import bundles of the above for common scenarios

Browse the full catalog at [**earthly.dev/lunar/guardrails/**](https://earthly.dev/lunar/guardrails/), or dive into the source in [`collectors/`](./collectors), [`policies/`](./policies), and [`catalogers/`](./catalogers).

> New to Lunar itself? Start at [**earthly.dev/lunar**](https://earthly.dev/lunar) for the platform overview.

---

## Where to Start

Start with a **starter pack** — a curated `lunar-config.yml` that's wired up and ready to drop into your repo. You can absolutely cherry-pick individual plugins instead, but most teams get going faster from a bundle and tune from there.

| Tier | What you get | Status |
|------|--------------|--------|
| **[Starter](./starter-packs/starter/)** | Zero config, zero secrets. Themed packs for Security, Code Quality, Cloud Native, AI Native, plus a Baseline. | **Available** — copy the `lunar-config.yml` and you're done. |
| **[Starter Plus](./starter-packs/starter-plus/)** | Adds vendor integrations (Snyk, SonarQube, Jira, PagerDuty, …). Light configuration, typically one token or URL per integration. | _Coming soon — [planned packs listed here](./starter-packs/starter-plus/)._ |
| **[Advanced](./starter-packs/advanced/)** | Specialized workflows (custom AST rules, OTel, GitOps, AI governance) that need meaningful configuration to be useful. | _Coming soon — [planned packs listed here](./starter-packs/advanced/)._ |

**Recommended path for new users:**

1. Read [`starter-packs/README.md`](./starter-packs/README.md) for the full tier breakdown.
2. Pick a Starter pack (try [**Baseline**](./starter-packs/starter/baseline/) if you can't decide).
3. Copy its `lunar-config.yml` into your repo root.
4. Tune enforcement levels (`score` → `report-pr` → `block-pr`) as your team gets comfortable.

---

## Repository Layout

```
lunar-lib/
├── starter-packs/   🚀 Curated, ready-to-use lunar-config.yml bundles
├── collectors/      🔍 Plugins that gather metadata into the Component JSON
├── policies/        ✅ Plugins that evaluate that metadata against standards
└── catalogers/      🗂️  Plugins that sync external component/ownership data
```

---

<div align="center">

Built and maintained by the team behind [Earthly](https://earthly.dev).

</div>
