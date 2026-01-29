# Plugin Landing Pages - Implementation Plan

Generate SEO-optimized landing pages for all Lunar plugins (collectors, policies, catalogers), similar to Zapier's integration pages. Each plugin gets its own page to drive organic search traffic.

---

## Table of Contents

1. [Goals](#goals)
2. [URL Structure](#url-structure)
3. [Metadata Location](#metadata-location)
4. [Metadata Schema](#metadata-schema)
5. [Build Pipeline Architecture](#build-pipeline-architecture)
6. [Validation Scripts](#validation-scripts)
7. [Template Design](#template-design)
8. [Styling Guidelines](#styling-guidelines)
9. [SEO Strategy](#seo-strategy)
10. [Implementation Phases](#implementation-phases)

---

## Goals

1. **SEO**: Capture long-tail search traffic for engineering standards topics (e.g., "kubernetes resource limits policy", "dockerfile latest tag enforcement")
2. **Discovery**: Help users find relevant plugins for their use cases
3. **Cross-linking**: Connect related collectors and policies to show complete guardrail solutions
4. **Low maintenance**: Content lives in lunar-lib; website just renders it

---

## URL Structure

Use "guardrails" as the umbrella marketing term:

```
earthly.dev/lunar/guardrails/                    # Index page (all guardrails)
earthly.dev/lunar/guardrails/collectors/         # Collector index
earthly.dev/lunar/guardrails/policies/           # Policy index  
earthly.dev/lunar/guardrails/catalogers/         # Cataloger index

earthly.dev/lunar/guardrails/collectors/github   # Individual collector
earthly.dev/lunar/guardrails/policies/container  # Individual policy
earthly.dev/lunar/guardrails/catalogers/github-org  # Individual cataloger
```

**Rationale:**
- "Guardrails" is a stronger marketing term that resonates with platform engineering teams
- It's the umbrella concept that ties collectors + policies together
- Aligns with potential future product naming updates

---

## Metadata Location

### Decision: Extend `lunar-*.yml` Files

Add SEO/landing page fields to existing plugin manifest files:
- `lunar-collector.yml`
- `lunar-policy.yml`
- `lunar-cataloger.yml`

**Why this approach:**
- Single source of truth per plugin (no separate SEO file to maintain)
- Existing files already have `name`, `description`, and sub-component lists
- Extend existing sub-components (`collectors:`, `policies:`, `catalogers:`) with SEO fields
- README stays focused on technical documentation

**Alternative considered:** README frontmatter
- Rejected because: Makes README harder to read, mixes documentation with marketing metadata

**Alternative considered:** Separate `landing-page.yml` file
- Rejected because: Adds another file to maintain per plugin, more scattered

---

## Metadata Schema

### Extended `lunar-collector.yml` Example

```yaml
version: 0

name: github
description: Collect GitHub repository settings and branch protection rules
author: earthly
default_image: earthly/lunar-lib:base-main

# === Landing page metadata ===
landing_page:
  display_name: "GitHub Collector"                 # Required, max 50 chars, must end with "Collector"
  long_description: |                              # Required, max 300 chars, used for hero tagline + meta description
    Automatically collect GitHub repository settings, branch protection rules, 
    and access permissions. Enforce VCS standards across your organization.
  category: "repository-and-ownership"             # Required, see categories below
  status: "beta"                                   # Required: stable|beta|experimental|deprecated
  icon: "assets/github.svg"                        # Required (templates fallback to placeholder if missing)
  
  # Related plugins for cross-linking (optional for collectors)
  related:
    - slug: "vcs"
      type: "policy"
      reason: "Enforces branch protection and merge strategy standards"  # Max 80 chars
    - slug: "github-org"
      type: "cataloger"
      reason: "Discovers all repositories in your GitHub organization"

# === Existing + extended sub-components ===
collectors:
  - name: repository
    description: |
      Collects basic GitHub repository settings:
      - Repository visibility (public, private, internal)
      - Default branch name
      - Topics and tags
      - Allowed merge strategies (merge, squash, rebase)
    mainBash: repository.sh
    hook:
      type: code
    keywords: ["github settings", "repository visibility", "merge strategies"]  # Required SEO keywords

  - name: branch-protection
    description: |
      Collects GitHub branch protection rules:
      - Required approvals and code owner review
      - Required status checks
      - Force push and deletion restrictions
    mainBash: branch_protection.sh
    hook:
      type: code
    keywords: ["branch protection", "code review", "github security", "required reviewers"]

  - name: access-permissions
    description: |
      Collects GitHub repository access permissions:
      - Direct collaborators with their permission levels
      - Teams with access and their permission levels
    mainBash: access_permissions.sh
    hook:
      type: code
    keywords: ["access control", "permissions", "audit", "least privilege"]
```

### Extended `lunar-policy.yml` Example

```yaml
version: 0

name: container
description: Container definition policies
author: earthly
default_image: earthly/lunar-lib:base-main

# === Landing page metadata ===
landing_page:
  display_name: "Container Policies"               # Required, max 50 chars, must end with "Policies"
  long_description: |                              # Required, max 300 chars, used for hero tagline + meta description
    Enforce container best practices including tag stability, registry allowlists, 
    required labels, and security configurations for Dockerfiles.
  category: "devex-build-and-ci"                   # Required
  status: "stable"                                 # Required
  icon: "assets/docker.svg"                        # Required (templates fallback to placeholder if missing)
  
  # Required collectors - policies MUST specify at least one
  requires:
    - slug: "dockerfile"
      type: "collector"
      reason: "Provides Dockerfile data that this policy evaluates"
  
  # Related plugins (optional)
  related:
    - slug: "k8s"
      type: "policy"
      reason: "Also enforces container resource limits in Kubernetes"

# === Existing + extended sub-policies ===
policies:
  - name: no-latest
    description: Container definitions should not use the :latest tag
    mainPython: no_latest.py
    keywords: ["dockerfile", "latest tag", "reproducible builds", "image tags"]

  - name: stable-tags
    description: Container definitions should use stable tags (digests or full semver)
    mainPython: stable_tags.py
    keywords: ["semver", "image digest", "version pinning", "tag policy"]

  - name: allowed-registries
    description: Container definitions should only use allowed registries
    mainPython: allowed_registries.py
    keywords: ["container registry", "supply chain security", "registry policy"]

  - name: healthcheck
    description: Container definitions should have HEALTHCHECK instruction
    mainPython: healthcheck.py
    keywords: ["healthcheck", "kubernetes", "container orchestration", "docker health"]

  - name: user
    description: Container definitions should specify USER instruction
    mainPython: user.py
    keywords: ["non-root", "container security", "least privilege", "USER instruction"]

inputs:
  allowed_registries:
    description: Comma-separated list of allowed registries
    default: "docker.io"
  required_labels:
    description: Comma-separated list of required labels (empty = no requirement)
    default: ""
```

### Extended `lunar-cataloger.yml` Example

```yaml
version: 0

name: github-org
description: Catalogs GitHub organization repositories as Lunar components
author: earthly
default_image: earthly/lunar-lib:github-org-main

# === Landing page metadata ===
landing_page:
  display_name: "GitHub Org Cataloger"             # Required, max 50 chars, must end with "Cataloger"
  long_description: |                              # Required, max 300 chars, used for hero tagline + meta description
    Sync repositories from GitHub organizations into your Lunar catalog. 
    Automatically track visibility, topics, and metadata across all repos.
  category: "repository-and-ownership"             # Required
  status: "stable"                                 # Required
  icon: "assets/github-org.svg"                    # Required (templates fallback to placeholder if missing)
  
  # Related plugins (optional for catalogers)
  related:
    - slug: "github"
      type: "collector"
      reason: "Collects detailed settings for each discovered repository"

# === Existing + extended sub-catalogers ===
catalogers:
  - name: repos
    description: |
      Syncs all repositories from a GitHub organization as components.
      - Maps GitHub topics to Lunar tags with configurable prefix
      - Supports filtering by visibility (public, private, internal)
      - Supports include/exclude patterns for repository names
    mainBash: main.sh
    hook:
      type: cron
      schedule: "0 2 * * *"
    keywords: ["service catalog", "auto-discovery", "github", "repository sync"]

inputs:
  org_name:
    description: GitHub organization name to sync (required)
  # ... other inputs unchanged
```

---

## Categories

Categories are **required** and must be one of the following (matching `ai-context/guardrail-specs/`):

| Category Slug | Display Name | Description |
|--------------|--------------|-------------|
| `repository-and-ownership` | Repository & Ownership | Documentation, CODEOWNERS, branch settings, catalog integration |
| `deployment-and-infrastructure` | Deployment & Infrastructure | Kubernetes, IaC, CD pipelines, infrastructure security |
| `testing-and-quality` | Testing & Quality | Unit tests, integration tests, coverage, test quality |
| `devex-build-and-ci` | DevEx, Build & CI | Golden paths, dependencies, images, artifacts, build quality |
| `security-and-compliance` | Security & Compliance | Scanning, vulnerabilities, SBOM, secrets, compliance frameworks |
| `operational-readiness` | Operational Readiness | Runbooks, on-call, observability, monitoring, resilience |

**Note:** Only single `category` is supported. The `categories` (plural) array was considered but rejected for simplicity.

---

## Status / Maturity

Plugins can declare their maturity status using the `status` field:

```yaml
landing_page:
  status: "stable"  # Required - must be one of the values below
```

| Status | Badge Color | Description |
|--------|-------------|-------------|
| `stable` | Green | Production ready, well tested, recommended for use |
| `beta` | Blue | Feature complete, may have minor issues, API stable |
| `experimental` | Amber | Early development, API may change, use with caution |
| `deprecated` | Red | No longer recommended, will be removed in future |

**Visual Language:**
- Status is shown as a small badge next to the type badge in the hero section
- Uses distinct colors for quick visual recognition
- Experimental/deprecated statuses show a tooltip with additional context

---

## Build Pipeline Architecture

### Overview

Guardrail data is **checked into the website repo** to keep builds fast. Developers can get started with just `npm install && npm start` without needing Earthly installed.

A nightly `+update-lunar-lib` target syncs the latest data from lunar-lib.

```
┌──────────────────────────────────────────────────────────────────────┐
│                           lunar-lib                                   │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  collectors/github/                                              │ │
│  │    ├── lunar-collector.yml  ← Contains landing_page + SEO fields │ │
│  │    ├── README.md            ← Technical documentation           │ │
│  │    └── assets/github.svg    ← Icon                              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                               │
          ┌────────────────────┴────────────────────┐
          │  Nightly sync (or manual trigger)       │
          │  +update-lunar-lib in earthly-website   │
          └────────────────────┬────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        earthly-website                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  src/_data/guardrails/                                        │   │
│  │    └── lunar-lib-data/      ← AUTO-GENERATED, do not edit    │   │
│  │        ├── collectors/                                        │   │
│  │        │   ├── github/                                        │   │
│  │        │   │   ├── lunar-collector.yml                        │   │
│  │        │   │   └── README.md                                  │   │
│  │        │   └── ...                                            │   │
│  │        ├── policies/                                          │   │
│  │        └── catalogers/                                        │   │
│  │                                                                │   │
│  │  src/assets/guardrails/                                       │   │
│  │    └── lunar-lib-icons/     ← AUTO-GENERATED, do not edit    │   │
│  │        ├── collectors/                                        │   │
│  │        │   ├── github/github.svg                              │   │
│  │        │   └── ast-grep/ast-grep.svg                          │   │
│  │        ├── policies/                                          │   │
│  │        └── catalogers/                                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                    ┌─────────▼─────────┐                            │
│                    │  npm run build    │  ← No Earthly needed!      │
│                    └─────────┬─────────┘                            │
│                              │                                       │
│                              ▼                                       │
│            ┌─────────────────────────────────────────────────────┐  │
│            │  Eleventy reads YAML via guardrails.js data file    │  │
│            │  and generates static HTML pages                    │  │
│            └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**Directory Naming Convention:**
- Directories prefixed with `lunar-lib-` are auto-generated by the sync process
- These should never be manually edited—changes will be overwritten
- This convention is documented in `earthly-website/AGENTS.md`

### earthly-website Earthfile: `+update-lunar-lib`

**Purpose:** Nightly sync (or manual trigger) to update checked-in guardrail data.

```bash
# Run manually or via nightly CI job
earthly +update-lunar-lib
git add src/_data/guardrails/lunar-lib-data/ src/assets/guardrails/lunar-lib-icons/
git commit -m "chore: sync lunar-lib guardrail data"
git push
```

**Implementation:**
- Imports lunar-lib Earthfile targets (`+guardrails-data`, `+guardrails-assets`)
- Copies `lunar-*.yml` + README files to `src/_data/guardrails/lunar-lib-data/{type}/{slug}/`
- Copies icons to `src/assets/guardrails/lunar-lib-icons/{type}/{slug}/` (preserving directory structure to avoid name clashes)
- Files are checked into git for fast, Earthly-free builds

### Website Build (no Earthly required)

Developers working on the website only need:
```bash
npm install
npm start   # or npm run build
```

Eleventy reads the checked-in YAML files directly using a JS data file (`src/_data/guardrails.js`) that:
- Walks `src/_data/guardrails/{collectors,policies,catalogers}/`
- Parses each `lunar-*.yml` using a JS YAML library (e.g., `js-yaml`)
- Extracts `landing_page:` and sub-component data
- Returns structured data for templates to consume

This keeps all data processing in JavaScript within the website repo.

---

## Validation Scripts

### `scripts/validate_landing_page_metadata.py` (lunar-lib)

Unified validator for all plugin types (collectors, policies, catalogers).

**Plugin-level validation:**
- `landing_page.display_name` required, max 50 chars, must end with type suffix:
  - Collectors: must end with "Collector" (e.g., "GitHub Collector")
  - Policies: must end with "Policies" (e.g., "Container Policies")
  - Catalogers: must end with "Cataloger" (e.g., "GitHub Org Cataloger")
- `landing_page.long_description` required, max 300 chars (used for hero tagline + meta description)
- `landing_page.category` required, must be one of the 6 valid categories
- `landing_page.icon` required (templates gracefully fallback to placeholders if missing)
- `landing_page.status` required, must be one of: stable, beta, experimental, deprecated
- `landing_page.related[].slug`, `.type`, `.reason` validated if present (optional)
- `landing_page.requires[]` required for policies only (must reference collectors)
- `landing_page.requires` is **disallowed** for collectors and catalogers

**Sub-component validation (collectors/policies/catalogers arrays):**
- `keywords` required, must be array

**Cross-validation (all errors, not warnings):**
- `related` or `requires` referencing non-existent plugins → error
- README title must match `display_name` exactly → error
- Unknown README sections (not in template) → error
- Disallowed README sections (Inputs, Secrets, Related Policies, etc.) → error

**Integration:**
- Integrated into `+lint` Earthfile target
- Exit non-zero on validation failures

### `scripts/validate_readme_structure.py` (lunar-lib)

Unified README validator for all plugin types (replaces individual enforce_*_readme_structure.py scripts).

**Validation rules:**
- README title must match `display_name` from YAML
- Required sections enforced per plugin type
- Disallowed sections (moved to YAML) cause errors:
  - Collectors: Inputs, Secrets, Related Policies, Related Collectors, Example Component JSON
  - Policies: Inputs, Related Collectors, Related Policies
  - Catalogers: Inputs, Secrets, Related Policies, Related Collectors

### `src/_data/guardrails.js` (earthly-website)

JavaScript data file that Eleventy loads automatically:

```javascript
// src/_data/guardrails.js
import yaml from 'js-yaml';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default function () {
    const types = ['collectors', 'policies', 'catalogers'];
    const guardrails = { collectors: [], policies: [], catalogers: [] };

    for (const type of types) {
        const dir = path.join(__dirname, 'guardrails', 'lunar-lib-data', type);
        if (!fs.existsSync(dir)) continue;

        for (const slug of fs.readdirSync(dir)) {
            const slugDir = path.join(dir, slug);
            if (!fs.statSync(slugDir).isDirectory()) continue;

            const ymlPath = path.join(slugDir, `lunar-${type.slice(0, -1)}.yml`);
            const mdPath = path.join(slugDir, 'README.md');

            if (fs.existsSync(ymlPath)) {
                const data = yaml.load(fs.readFileSync(ymlPath, 'utf8'));
                const readme = fs.existsSync(mdPath) ? fs.readFileSync(mdPath, 'utf8') : '';
                guardrails[type].push({ slug, ...data, readme });
            }
        }
    }

    return guardrails;
}
```

This provides `guardrails.collectors`, `guardrails.policies`, `guardrails.catalogers` to all templates.

---

## Template Design

### Eleventy Page Generation

Eleventy uses `.njk` (Nunjucks) template files as source, which compile to static `.html` at build time. There's no client-side hydration—pages are fully static HTML.

For dynamic page generation from data, Eleventy uses [pagination](https://www.11ty.dev/docs/pagination/). A single `.njk` template can generate multiple HTML pages from the `guardrails` data.

### File Structure in earthly-website

```
src/
├── _data/
│   ├── guardrails.js                      # JS data file (parses YAML, see above)
│   └── guardrails/
│       └── lunar-lib-data/                # ⚠️ AUTO-GENERATED - do not edit
│           ├── collectors/{slug}/
│           │   ├── lunar-collector.yml
│           │   └── README.md
│           ├── policies/{slug}/
│           └── catalogers/{slug}/
├── lunar/
│   └── guardrails/
│       ├── index.njk                      # All guardrails index → /lunar/guardrails/
│       ├── collectors.njk                 # Collector list → /lunar/guardrails/collectors/
│       ├── collector.njk                  # Paginated detail → /lunar/guardrails/collectors/{slug}/
│       ├── policies.njk                   # Policy list (TODO)
│       ├── policy.njk                     # Paginated detail (TODO)
│       ├── catalogers.njk                 # Cataloger list (TODO)
│       └── cataloger.njk                  # Paginated detail (TODO)
└── assets/
    ├── css/
    │   ├── guardrails.css                 # Common styles (badges, hero, breadcrumbs)
    │   ├── guardrails-index.css           # Main index page styles
    │   ├── collectors.css                 # Collectors list page styles
    │   └── collector.css                  # Individual collector page styles
    ├── js/
    │   ├── collectors.js                  # Category filtering, URL hash handling
    │   └── collector.js                   # Copy-to-clipboard for uses line
    └── guardrails/
        └── lunar-lib-icons/               # ⚠️ AUTO-GENERATED - do not edit
            ├── collectors/{slug}/{icon}.svg
            ├── policies/{slug}/{icon}.svg
            └── catalogers/{slug}/{icon}.svg
```

### Pagination Example

```njk
---
pagination:
  data: guardrails.collectors
  size: 1
  alias: collector
permalink: "lunar/guardrails/collectors/{{ collector.slug }}/"
---
{% extends "guardrails/base.njk" %}

{% block content %}
  <h1>{{ collector.landing_page.display_name }}</h1>
  <p>{{ collector.landing_page.long_description }}</p>
  {{ collector.readme | markdown | safe }}
{% endblock %}
```

This generates one HTML page per collector from the data.

### Individual Plugin Page Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  [Navbar]                                                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Lunar > Guardrails > Collectors > GitHub                      │ │
│  │                                                                 │ │
│  │  [Icon]  {display_name}                                         │ │
│  │          {TYPE} · {category}                                    │ │
│  │                                                                 │ │
│  │  {long_description}                                             │ │
│  │                                                                 │ │
│  │  [Get Started →]  [View on GitHub →]                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  HOW {TYPE}S FIT INTO LUNAR                                    │ │
│  │                                                                 │ │
│  │  (Same content for all plugins of this type - see below)       │ │
│  │  Brief explanation of Lunar's guardrails engine and how        │ │
│  │  this plugin type contributes to the overall workflow.         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  WHAT'S INCLUDED                                               │ │
│  │                                                                 │ │
│  │  Cards for each sub-component (from collectors:/policies:)     │ │
│  │  Each card shows: seo_title, seo_description, seo_keywords     │ │
│  │                                                                 │ │
│  │  ┌─────────────────────────────────────────────────────────┐   │ │
│  │  │ {sub.seo_title}                                          │   │ │
│  │  │ {sub.seo_description}                                    │   │ │
│  │  │ [keyword] [keyword] [keyword]                            │   │ │
│  │  └─────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  FULL DOCUMENTATION                                            │ │
│  │                                                                 │ │
│  │  The plugin's README.md rendered as HTML                       │ │
│  │  (already designed to be marketing-friendly)                   │ │
│  │                                                                 │ │
│  │  Includes: Overview, Collected/Synced Data tables, Example     │ │
│  │  JSON, Inputs, Secrets, Installation YAML, Remediation, etc.   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────┐  ┌───────────────────────────────┐ │
│  │  RELATED POLICIES           │  │  RELATED COLLECTORS           │ │
│  │                             │  │                               │ │
│  │  From landing_page.related  │  │  From landing_page.related    │ │
│  │  [Icon] {display_name}      │  │  [Icon] {display_name}        │ │
│  │  {reason}                   │  │  {reason}                     │ │
│  │  [View →]                   │  │  [View →]                     │ │
│  └─────────────────────────────┘  └───────────────────────────────┘ │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  [CTA Section: Book a Demo]                                         │
├──────────────────────────────────────────────────────────────────────┤
│  [Footer]                                                            │
└──────────────────────────────────────────────────────────────────────┘
```

### Type-Specific Context Sections

Each plugin type gets a short intro explaining how it fits into the Lunar ecosystem. This content lives in the website templates (not in lunar-lib) and is the same for all plugins of that type.

Each section should include a simple diagram or visual showing where this plugin type fits in the Lunar data flow (e.g., Collectors → Component JSON → Policies → PR Feedback).

**Collector Context (for all collector pages):**
> **What is a Collector?**
> Lunar collectors gather metadata from your codebase, CI/CD pipelines, and external systems. They run automatically on code changes or on a schedule, extracting structured data into the Component JSON—a normalized representation of your application's posture. This data is then evaluated by policies to enforce your engineering standards.

**Policy Context (for all policy pages):**
> **What is a Policy?**
> Lunar policies define your engineering standards as code. They evaluate data collected by collectors and produce pass/fail checks with actionable feedback. Policies support gradual enforcement—from silent scoring to blocking PRs or deployments—letting you roll out standards at your own pace.

**Cataloger Context (for all cataloger pages):**
> **What is a Cataloger?**
> Lunar catalogers sync component metadata from external systems into your Lunar catalog. They run on a schedule to keep your catalog up-to-date with repository lists, ownership data, and tags from sources like GitHub organizations or service registries.

### Index Page Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  Lunar Guardrails                                                  │
│  100+ pre-built collectors, policies, and catalogers               │
│                                                                    │
│  [Filter: All | Collectors | Policies | Catalogers]               │
│  [Filter by category: dropdown]                                    │
│                                                                    │
│  Grid of plugin cards, each showing:                               │
│  - Icon                                                            │
│  - display_name                                                    │
│  - Type badge (Collector/Policy/Cataloger)                         │
│  - Category badge                                                  │
│  - long_description                                                │
└────────────────────────────────────────────────────────────────────┘
```

---

## Styling Guidelines

Follow the existing Earthly website design language (from `COLOR-PALETTE.md`).

---

## SEO Strategy

### On-Page SEO

1. **Title Tags**: `{seo_title} | Earthly Lunar` (suffix appended automatically by website)

2. **Meta Descriptions**: From `seo_description` field

3. **Keywords**: Aggregated from all `seo_keywords` arrays within sub-components

4. **Schema Markup** (JSON-LD): SoftwareApplication type with name, description, publisher

### Keyword Strategy by Category

| Category | Target Keywords |
|----------|-----------------|
| Repository & Ownership | "github branch protection", "codeowners validation", "repository standards" |
| Deployment & Infrastructure | "kubernetes resource limits", "terraform policy", "infrastructure compliance" |
| Testing & Quality | "test coverage enforcement", "ci quality gates", "code coverage policy" |
| DevEx, Build & CI | "dockerfile best practices", "container security", "build reproducibility" |
| Security & Compliance | "sbom generation", "vulnerability scanning", "nist ssdf compliance" |
| Operational Readiness | "structured logging", "health checks", "observability standards" |

---

## Implementation Phases

### Phase 1: End-to-End Proof of Concept (One Plugin)

Get one complete page live with minimal implementation. Skip strict validation, use basic CSS.

**lunar-lib:**
- [x] Add `landing_page:` section to `collectors/github/lunar-collector.yml`:
  - Top-level: `display_name`, `long_description`, `category`, `icon`
  - Sub-components: `keywords` for each collector
- [x] Create/source `collectors/github/assets/github.svg` icon
- [x] Remove "Related Policies" section from `collectors/github/README.md` (now in YAML)
- [x] Add `landing_page:` section to `collectors/ast-grep/lunar-collector.yml` (second example with inputs)
- [x] Create/source `collectors/ast-grep/assets/ast-grep.svg` icon
- [x] Add `example_component_json` field to github and ast-grep YAMLs
- [x] Add `secrets` field to github YAML
- [x] Remove "Example Component JSON output", "Inputs", "Secrets" from github and ast-grep READMEs

**earthly-website:**
- [x] Create `+update-lunar-lib` target in Earthfile (copies files from lunar-lib)
- [x] Run sync, check in initial `src/_data/guardrails/collectors/github/` directory
- [x] Create `src/_data/guardrails.js` (JS data file to parse YAML)
- [x] Create minimal `base.njk` template (header, long_description, README content, meta tags, footer)
- [x] Create paginated collector template at `lunar/guardrails/collector.njk`
- [x] Add basic `guardrails.css` (readable layout, minimal styling)

**Checkpoint:** Local review before proceeding.

---

### Phase 2: Expand to All Plugins (After Review Approval)

Once Phase 1 passes review, scale to all plugins.

**lunar-lib - Collectors (DONE):**
- [x] Add `landing_page:` + `keywords` to all collectors (6 total)
- [x] Simplified schema: `display_name` (with suffix), `long_description`, `category`, `status`
- [x] Sub-collectors: use `name`, `description`, `keywords` (removed seo_title, seo_description)
- [x] Add `example_component_json` field to all collector YAMLs
- [x] Add `secrets` field to collectors that have secrets
- [x] Update all collector READMEs:
  - [x] Remove "Example Component JSON output" sections
  - [x] Remove "Inputs" sections
  - [x] Remove "Secrets" sections
  - [x] Remove "Related Policies/Collectors" sections
  - [x] Update titles to match `display_name`
- [x] Create/source icon SVGs for each collector

**lunar-lib - Policies (DONE):**
- [x] Add `landing_page:` section to all policy YAMLs with:
  - `display_name` ending with "Policies" (e.g., "Container Policies")
  - `long_description`, `category`, `status`
  - `requires:` array (REQUIRED - must reference at least one collector)
  - `related:` array (optional)
- [x] Add `keywords` to sub-policies
- [x] Add `inputs` field (move from READMEs)
- [x] Update all policy READMEs:
  - Remove "Related Collectors" sections
  - Remove "Inputs" sections
  - Update titles to match `display_name`
- [x] Create/source icon SVGs for each policy

**lunar-lib - Catalogers (DONE):**
- [x] Add `landing_page:` section to all cataloger YAMLs with:
  - `display_name` ending with "Cataloger" (e.g., "GitHub Org Cataloger")
  - `long_description`, `category`, `status`
  - `related:` array (optional)
- [x] Add `keywords` to sub-catalogers
- [x] Add `example_catalog_json` field (catalog entry example, different from Component JSON)
- [ ] Add `inputs` and `secrets` fields (move from READMEs)
- [x] Update all cataloger READMEs:
  - Remove "Related" sections
  - Remove "Inputs" sections
  - Remove "Secrets" sections
  - Update titles to match `display_name`
- [x] Create/source icon SVGs for each cataloger

**lunar-lib - Templates (TODO):**
- [x] Update `ai-context/collector-README-template.md`:
  - Remove "Related Policies" section
  - Remove "Inputs" section
  - Remove "Secrets" section
  - Remove "Example Component JSON output" collapsible
- [x] Update `ai-context/policy-README-template.md`:
  - Remove "Related Collectors" section
  - Remove "Inputs" section (if present)
  - Remove "Example Component JSON output" collapsible
- [x] Update `ai-context/cataloger-README-template.md`:
  - Remove "Related" sections
  - Remove "Inputs" section
  - Remove "Secrets" section
  - Remove "Example Component JSON output" collapsible

**earthly-website:**
- [x] Run full sync, check in all guardrail data
- [x] Create main index page (`/lunar/guardrails/`)
- [x] Create collectors list page (`/lunar/guardrails/collectors/`)
- [x] Add category filtering to collectors list page
- [x] Wire up meta descriptions from `long_description` in templates
- [x] Add JSON-LD structured data to list pages
- [x] Add canonical URLs and Open Graph meta tags
- [x] Update collector.njk template for simplified schema
- [x] Add graceful icon fallback (placeholder symbols when icons missing)
- [x] Create paginated templates for policies (`policy.njk`)
- [x] Create paginated templates for catalogers (`cataloger.njk`)
- [ ] Create policies list page (`/lunar/guardrails/policies/`)
- [ ] Create catalogers list page (`/lunar/guardrails/catalogers/`)
- [ ] Add category filtering to policies and catalogers list pages
- [x] Add "Requires" section to policy pages (show required collectors)

---

### Phase 3: Polish & Validation

**lunar-lib - Validation (DONE):**
- [x] Create `scripts/validate_landing_page_metadata.py` (unified for all plugin types)
  - Validates display_name suffix, long_description, category
  - Validates `requires` for policies (must have at least one collector)
  - Cross-validates related/requires references exist
  - Validates README title matches display_name
- [x] Create `scripts/validate_readme_structure.py` (unified, replaces individual scripts)
  - Validates required sections per plugin type
  - Errors on disallowed sections (Inputs, Secrets, Related, etc.)
  - Errors on unknown sections
- [x] Integrate validation into `+lint` Earthfile target
- [x] Remove old individual enforce_*_readme_structure.py scripts

**Templates:**
- [x] Add "What's Included" section with sub-component cards
- [x] Add "Related Plugins" cross-linking section
- [x] Add type-specific context sections (collector/policy/cataloger intros)
- [x] Add "Example Collected Data" section with collapsible JSON preview
- [x] Add "Configuration" section with inputs table and secrets table
- [x] Add copy-to-clipboard buttons for all code blocks
- [x] Support single category (plural `categories` array rejected for simplicity)

**Styling:**
- [x] Full CSS with type colors, category badges, card styling
  - `guardrails.css` - Common styles (badges, hero sections, breadcrumbs)
  - `guardrails-index.css` - Main index page (tech cloud, plugin grid, flow diagram)
  - `collectors.css` - Collectors list page (filter bar, item cards)
  - `collector.css` - Individual collector page (detail sections)
- [x] Responsive layout for mobile
- [x] Dark mode consistency with rest of site

**SEO:**
- [x] Add JSON-LD schema markup (BreadcrumbList, SoftwareSourceCode, FAQPage)
- [x] Verify title tag format
- [x] Dynamic canonical URLs per page
- [x] Dynamic Open Graph URLs per page
- [x] Meta keywords from seo_keywords data
- [x] Article meta tags (publisher, section, tags)
- [x] Robots meta tag with optimal crawl directives
- [x] Microdata (itemscope/itemprop) on hero section and breadcrumbs
- [x] Improved alt text with context on images

---

### Phase 4: Automation & Maintenance

- [ ] Set up nightly GitHub Actions workflow to run `+update-lunar-lib` and create PR if changes
- [x] Add cross-validation for `related` plugin references (now an error, not warning)
- [ ] Add client-side search (Lunr.js)

---

### Phase 5: Granular Sub-Policy + Collector Pages

Create dynamic landing pages for every combination of sub-policy + required collector. This provides highly targeted SEO pages for specific guardrail use cases.

**Examples:**
- `/lunar/guardrails/codecov/ensure-ran/` - Codecov collector + "ensure coverage ran" sub-policy
- `/lunar/guardrails/github/default-branch-main/` - GitHub collector + "default branch is main" sub-policy
- `/lunar/guardrails/dockerfile/no-latest/` - Dockerfile collector + "no latest tag" sub-policy
- `/lunar/guardrails/k8s/resource-limits/` - Kubernetes collector + "resource limits" sub-policy

**Benefits:**
- Captures long-tail searches like "how to enforce main branch on github"
- Shows the complete collector → policy workflow for a specific check
- Provides copy-paste configuration for enabling a single guardrail

**TODO:**
- [ ] Design URL structure for sub-policy + collector combinations
- [ ] Determine data source: derive from `requires` relationships in policy YAMLs
- [ ] Create paginated template for combination pages
- [ ] Add cross-linking from parent collector/policy pages (call these "use-cases")
- [ ] Add to sitemap and internal linking structure

---

## Schema Simplifications (Implemented)

During implementation, the schema was simplified from the original plan:

| Original Field | New Field | Notes |
|----------------|-----------|-------|
| `seo_title` | (removed) | Use `display_name` for page titles |
| `seo_description` | `long_description` | Clearer naming, max 300 chars |
| `display_name` | `display_name` + suffix | Must end with "Collector", "Policies", or "Cataloger" |
| Sub-component `seo_title` | (removed) | Use `name` directly |
| Sub-component `seo_description` | (removed) | Use `description` directly |
| Sub-component `seo_keywords` | `keywords` | Simpler naming |
| `icon` | `icon` | Required by validator, templates fallback to placeholders |
| `tagline` | (removed) | `long_description` serves as both meta description and hero tagline |
| `status` | `status` | Now required (was optional with default) |
| `keywords` | `keywords` | Now required for sub-components (was optional) |
| `related` (for policies) | `requires` + `related` | Policies must have `requires` for collectors |

**Rationale:**
- Reduced duplication between SEO fields and existing name/description
- `display_name` with suffix ensures consistent naming across types
- `requires` makes the collector dependency explicit for policies (disallowed for collectors/catalogers)
- Simpler sub-component schema reduces maintenance burden
- `tagline` removed (redundant with `long_description`)
- `status` and `keywords` made strictly required
- Templates gracefully handle missing icons with placeholder symbols

---

## Open Questions

1. **Icon sourcing**: ~~Create new SVGs or use existing assets?~~ **DONE**
   - Icon field is required by validator
   - Templates gracefully fallback to placeholder symbols (↓ for collectors, ✓ for policies, ⇄ for catalogers)
   - All collectors have icons: ast-grep, github, codecov, dockerfile, golang, readme
   - All policies have icons: container (docker), coverage, readme, vcs
   - All catalogers have icons: github-org (reuses github icon)
   - Icons must have transparent backgrounds with solid shapes (CSS filter flattens to white)
