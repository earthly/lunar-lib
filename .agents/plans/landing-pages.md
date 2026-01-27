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

# === Landing page metadata (NEW fields) ===
landing_page:
  display_name: "GitHub Repository Settings"       # Required, max 50 chars
  tagline: "Collect GitHub repository settings and branch protection rules"  # Required, max 100 chars
  seo_title: "GitHub Repository Collector"         # Required, max 50 chars (website appends "| Earthly Lunar")
  seo_description: |                               # Required, max 160 chars
    Automatically collect GitHub repository settings, branch protection rules, 
    and access permissions. Enforce VCS standards across your organization.
  category: "repository-and-ownership"             # Required, see categories below
  icon: "assets/github.svg"                        # Required, relative to plugin dir
  
  # Related plugins for cross-linking
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
    
    # NEW: SEO fields for this sub-collector
    seo_title: "Collect Repository Settings"                    # Max 60 chars
    seo_description: |                                           # Max 200 chars
      Automatically collect repository visibility, default branch, topics, 
      and merge strategies from all GitHub repositories.
    seo_keywords: ["github settings", "repository visibility", "merge strategies"]

  - name: branch-protection
    description: |
      Collects GitHub branch protection rules:
      - Required approvals and code owner review
      - Required status checks
      - Force push and deletion restrictions
    mainBash: branch_protection.sh
    hook:
      type: code
    
    # NEW: SEO fields
    seo_title: "Enforce Branch Protection Standards"
    seo_description: |
      Collect branch protection settings from all repositories and verify 
      they meet your organization's security requirements.
    seo_keywords: ["branch protection", "code review", "github security", "required reviewers"]

  - name: access-permissions
    description: |
      Collects GitHub repository access permissions:
      - Direct collaborators with their permission levels
      - Teams with access and their permission levels
    mainBash: access_permissions.sh
    hook:
      type: code
    
    # NEW: SEO fields
    seo_title: "Audit Repository Access Controls"
    seo_description: |
      Track who has access to each repository and at what permission level. 
      Identify over-permissioned users and ensure least-privilege access.
    seo_keywords: ["access control", "permissions", "audit", "least privilege"]
```

### Extended `lunar-policy.yml` Example

```yaml
version: 0

name: container
description: Container definition policies
author: earthly
default_image: earthly/lunar-lib:base-main

# === Landing page metadata (NEW) ===
landing_page:
  display_name: "Container Security"
  tagline: "Enforce Dockerfile best practices and container security standards"
  seo_title: "Container Security Policies"
  seo_description: |
    Enforce container best practices including tag stability, registry allowlists, 
    required labels, and security configurations for Dockerfiles.
  category: "devex-build-and-ci"
  icon: "assets/docker.svg"
  
  related:
    - slug: "dockerfile"
      type: "collector"
      reason: "Collects Dockerfile data that this policy evaluates"

# === Existing + extended sub-policies ===
policies:
  - name: no-latest
    description: Container definitions should not use the :latest tag
    mainPython: no_latest.py
    
    # NEW: SEO fields
    seo_title: "Prevent :latest Tags"
    seo_description: |
      Block Dockerfiles that use implicit or explicit :latest tags, 
      ensuring reproducible builds and avoiding surprise updates.
    seo_keywords: ["dockerfile", "latest tag", "reproducible builds", "image tags"]

  - name: stable-tags
    description: Container definitions should use stable tags (digests or full semver)
    mainPython: stable_tags.py
    
    # NEW: SEO fields
    seo_title: "Require Stable Image Tags"
    seo_description: |
      Enforce full semver (1.2.3) or digest (sha256:...) tags for all 
      base images, preventing version drift across environments.
    seo_keywords: ["semver", "image digest", "version pinning", "tag policy"]

  - name: allowed-registries
    description: Container definitions should only use allowed registries
    mainPython: allowed_registries.py
    
    # NEW: SEO fields
    seo_title: "Registry Allowlist"
    seo_description: |
      Ensure all container images come from approved registries, 
      preventing supply chain attacks from untrusted sources.
    seo_keywords: ["container registry", "supply chain security", "registry policy"]

  - name: healthcheck
    description: Container definitions should have HEALTHCHECK instruction
    mainPython: healthcheck.py
    
    # NEW: SEO fields
    seo_title: "Require HEALTHCHECK"
    seo_description: |
      Verify containers define health checks for orchestrator integration 
      and automatic recovery from unhealthy states.
    seo_keywords: ["healthcheck", "kubernetes", "container orchestration", "docker health"]

  - name: user
    description: Container definitions should specify USER instruction
    mainPython: user.py
    
    # NEW: SEO fields
    seo_title: "Non-Root Containers"
    seo_description: |
      Ensure containers run as non-root users, reducing attack surface 
      and meeting security compliance requirements.
    seo_keywords: ["non-root", "container security", "least privilege", "USER instruction"]

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

# === Landing page metadata (NEW) ===
landing_page:
  display_name: "GitHub Organization Sync"
  tagline: "Automatically catalog all repositories from your GitHub organization"
  seo_title: "GitHub Organization Cataloger"
  seo_description: |
    Sync repositories from GitHub organizations into your Lunar catalog. 
    Automatically track visibility, topics, and metadata across all repos.
  category: "repository-and-ownership"
  icon: "assets/github-org.svg"
  
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
    
    # NEW: SEO fields
    seo_title: "Auto-Discover Repositories"
    seo_description: |
      Automatically add new repositories to your catalog as they're created, 
      ensuring complete coverage without manual registration.
    seo_keywords: ["service catalog", "auto-discovery", "github", "repository sync"]

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
│  │  src/_data/guardrails/        ← CHECKED INTO GIT             │   │
│  │    ├── collectors/                                            │   │
│  │    │   ├── github/                                            │   │
│  │    │   │   ├── lunar-collector.yml  (copied from lunar-lib)   │   │
│  │    │   │   └── README.md                                      │   │
│  │    │   └── ...                                                │   │
│  │    ├── policies/                                              │   │
│  │    └── catalogers/                                            │   │
│  │                                                                │   │
│  │  src/assets/guardrails/       ← CHECKED INTO GIT             │   │
│  │    ├── github.svg                                             │   │
│  │    └── ...                                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                    ┌─────────▼─────────┐                            │
│                    │  npm run build    │  ← No Earthly needed!      │
│                    └─────────┬─────────┘                            │
│                              │                                       │
│                              ▼                                       │
│            ┌─────────────────────────────────────────┐              │
│            │  Eleventy reads YAML directly via JS    │              │
│            │  data files and generates HTML pages    │              │
│            └─────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────────────────┘
```

### earthly-website Earthfile: `+update-lunar-lib`

**Purpose:** Nightly sync (or manual trigger) to update checked-in guardrail data.

```bash
# Run manually or via nightly CI job
earthly +update-lunar-lib
git add src/_data/guardrails/ src/assets/guardrails/
git commit -m "chore: sync lunar-lib guardrail data"
git push
```

**Implementation:**
- Clone/pull `lunar-lib` repo (or fetch via GitHub API)
- Copy `lunar-*.yml` files to `src/_data/guardrails/{type}/{slug}/`
- Copy README.md files alongside the YAML
- Copy icons to `src/assets/guardrails/{slug}.svg`
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

Validates all `lunar-*.yml` files have complete landing page metadata:

**Plugin-level validation:**
- `landing_page.display_name` required, max 50 chars
- `landing_page.tagline` required, max 100 chars
- `landing_page.seo_title` required, max 50 chars
- `landing_page.seo_description` required, max 160 chars
- `landing_page.category` required, must be one of the 6 valid categories
- `landing_page.icon` required, file must exist
- `landing_page.related[].slug`, `.type`, `.reason` validated if present

**Sub-component validation (collectors/policies/catalogers arrays):**
- Each sub-component must have `seo_title` (max 60 chars)
- Each sub-component must have `seo_description` (max 200 chars)
- Each sub-component must have `seo_keywords` (array, at least 1 keyword)

**Cross-validation:**
- Warn if `related` references plugins that don't exist

**Integration:**
- Add to existing `+lint` Earthfile target
- Exit non-zero on validation failures

### `src/_data/guardrails.js` (earthly-website)

JavaScript data file that Eleventy loads automatically:

```javascript
// src/_data/guardrails.js
const yaml = require('js-yaml');
const fs = require('fs');
const path = require('path');

module.exports = function() {
  const types = ['collectors', 'policies', 'catalogers'];
  const guardrails = { collectors: [], policies: [], catalogers: [] };
  
  for (const type of types) {
    const dir = path.join(__dirname, 'guardrails', type);
    if (!fs.existsSync(dir)) continue;
    
    for (const slug of fs.readdirSync(dir)) {
      const ymlPath = path.join(dir, slug, `lunar-${type.slice(0,-1)}.yml`);
      const mdPath = path.join(dir, slug, 'README.md');
      
      if (fs.existsSync(ymlPath)) {
        const data = yaml.load(fs.readFileSync(ymlPath, 'utf8'));
        const readme = fs.existsSync(mdPath) ? fs.readFileSync(mdPath, 'utf8') : '';
        guardrails[type].push({ slug, ...data, readme });
      }
    }
  }
  return guardrails;
};
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
├── _includes/
│   └── guardrails/
│       ├── base.njk                # Base layout for all guardrail pages
│       ├── collector.njk           # Collector-specific sections
│       ├── policy.njk              # Policy-specific sections
│       ├── cataloger.njk           # Cataloger-specific sections
│       ├── sub-component-card.njk  # Reusable card for sub-collectors/policies
│       └── related.njk             # Cross-links section
├── _data/
│   ├── guardrails.js               # JS data file (parses YAML, see above)
│   └── guardrails/                 # Raw data synced from lunar-lib
│       ├── collectors/
│       │   └── github/
│       │       ├── lunar-collector.yml
│       │       └── README.md
│       ├── policies/
│       └── catalogers/
├── lunar/
│   └── guardrails/
│       ├── index.njk               # All guardrails index → /lunar/guardrails/
│       ├── collectors.njk          # Collector index → /lunar/guardrails/collectors/
│       ├── collector.njk           # Paginated template → /lunar/guardrails/collectors/{slug}/
│       ├── policies.njk            # Policy index
│       ├── policy.njk              # Paginated template
│       ├── catalogers.njk          # Cataloger index
│       └── cataloger.njk           # Paginated template
└── assets/
    ├── css/
    │   └── guardrails.css
    └── guardrails/                 # Icons synced from lunar-lib
        ├── github.svg
        └── ...
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
  <p>{{ collector.landing_page.tagline }}</p>
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
│  │  {tagline}                                                      │ │
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
│  - tagline                                                         │
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
- [ ] Add `landing_page:` section to `collectors/github/lunar-collector.yml`:
  - Top-level: `display_name`, `tagline`, `seo_title`, `seo_description`, `category`, `icon`
  - Sub-components: `seo_title`, `seo_description`, `seo_keywords` for each collector
- [ ] Create/source `collectors/github/assets/github.svg` icon
- [ ] Remove "Related Policies" section from `collectors/github/README.md` (now in YAML)

**earthly-website:**
- [ ] Create `+update-lunar-lib` target in Earthfile (copies files from lunar-lib)
- [ ] Run sync, check in initial `src/_data/guardrails/collectors/github/` directory
- [ ] Create `src/_data/guardrails.js` (JS data file to parse YAML)
- [ ] Create minimal `base.njk` template (header, tagline, README content, meta tags, footer)
- [ ] Create paginated collector template at `lunar/guardrails/collector.njk`
- [ ] Add basic `guardrails.css` (readable layout, minimal styling)

**Checkpoint:** Local review before proceeding.

---

### Phase 2: Expand to All Plugins (After Review Approval)

Once Phase 1 passes review, scale to all plugins.

**lunar-lib:**
- [ ] Add `landing_page:` + sub-component SEO fields to remaining collectors
- [ ] Add `landing_page:` + sub-component SEO fields to all policies
- [ ] Add `landing_page:` + sub-component SEO fields to all catalogers
- [ ] Create/source icon SVGs for each plugin
- [ ] Remove "Related Policies/Collectors" sections from all READMEs (now in YAML)
- [ ] Update `ai-context/collector-README-template.md`: remove "Related Policies" section
- [ ] Update `ai-context/policy-README-template.md`: remove "Related Collectors" section
- [ ] Update `scripts/enforce_collector_readme_structure.py`:
  - Remove `"Related Policies"` from `TEMPLATE_SECTIONS` entirely
  - Remove validation logic for this section (lines 659-693)
- [ ] Update `scripts/enforce_policy_readme_structure.py`:
  - Remove `"Related Collectors"` from `TEMPLATE_SECTIONS` entirely
  - Remove validation logic for this section (lines 626-655)

**earthly-website:**
- [ ] Run full sync, check in all guardrail data
- [ ] Create paginated templates for policies and catalogers
- [ ] Create index pages (`/guardrails/`, `/guardrails/collectors/`, etc.)
- [ ] Add category filtering to index pages
- [ ] Wire up meta descriptions from `seo_description` in templates

---

### Phase 3: Polish & Validation

**lunar-lib:**
- [ ] Create `scripts/validate_landing_page_metadata.py` (strict validation)
- [ ] Integrate validation into `+lint` target

**Templates:**
- [ ] Add "What's Included" section with sub-component cards
- [ ] Add "Related Plugins" cross-linking section
- [ ] Add type-specific context sections (collector/policy/cataloger intros)

**Styling:**
- [ ] Full `guardrails.css` with type colors, category badges, card styling
- [ ] Responsive layout for mobile
- [ ] Dark mode consistency with rest of site

**SEO:**
- [ ] Add JSON-LD schema markup
- [ ] Verify title tag format

---

### Phase 4: Automation & Maintenance

- [ ] Set up nightly GitHub Actions workflow to run `+update-lunar-lib` and create PR if changes
- [ ] Add cross-validation for `related` plugin references
- [ ] Add client-side search (Lunr.js)

---

## Open Questions

1. **Icon sourcing**: Create new SVGs or use existing assets?
  It's going to be manual (user researches online). In some cases, generate simple consistent SVG icons, in other cases use an emoji (but generally avoid emojis)
