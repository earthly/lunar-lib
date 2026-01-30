# Landing Pages v2 - Terminology & Structure Revision

This plan describes changes to the existing landing pages implementation to simplify terminology and improve information architecture.

---

## Table of Contents

1. [Background](#background)
2. [Problem Statement](#problem-statement)
3. [Terminology Changes](#terminology-changes)
4. [URL Structure](#url-structure)
5. [Page Structure Changes](#page-structure-changes)
6. [Categories](#categories)
7. [Implementation Phases](#implementation-phases)

---

## Background

### Goals

1. **SEO**: Capture long-tail search traffic for engineering standards topics (e.g., "kubernetes resource limits policy", "dockerfile latest tag enforcement")
2. **Discovery**: Help users find relevant integrations and guardrails for their use cases
3. **Cross-linking**: Connect related collectors and policies to show complete guardrail solutions
4. **Low maintenance**: Content lives in lunar-lib; website just renders it

### Data Architecture

All landing page data lives in **lunar-lib** and is synced to **earthly-website** via a nightly `+update-lunar-lib` Earthfile target:

```
lunar-lib/                              earthly-website/
├── collectors/{slug}/                  src/_data/guardrails/lunar-lib-data/
│   ├── lunar-collector.yml     ──►     ├── collectors/{slug}/
│   ├── README.md                       │   ├── lunar-collector.yml
│   └── assets/{icon}.svg               │   └── README.md
├── policies/{slug}/                    ├── policies/{slug}/
└── catalogers/{slug}/                  └── catalogers/{slug}/

                                        src/assets/guardrails/lunar-lib-icons/
                                        ├── collectors/{slug}/{icon}.svg
                                        ├── policies/{slug}/{icon}.svg
                                        └── catalogers/{slug}/{icon}.svg
```

- Directories prefixed with `lunar-lib-` are **auto-generated** and should never be manually edited
- Eleventy reads YAML files via `src/_data/guardrails.js` and generates static HTML pages
- Website builds require only `npm install && npm start` (no Earthly needed)

### Metadata Schema (Already Implemented)

Each collector/policy/cataloger has a `lunar-*.yml` file with a `landing_page:` section:

```yaml
# lunar-collector.yml / lunar-policy.yml / lunar-cataloger.yml
landing_page:
  display_name: "GitHub Collector"       # Required, max 50 chars
  long_description: |                    # Required, max 300 chars (hero tagline + meta description)
    Automatically collect GitHub repository settings, branch protection rules,
    and access permissions. Enforce VCS standards across your organization.
  category: "repository-and-ownership"   # Required (see Categories section)
  status: "stable"                       # Required: stable|beta|experimental|deprecated
  icon: "assets/github.svg"              # Required (fallback to placeholder if missing)
  
  # For policies only — required collectors
  requires:
    - slug: "github"
      type: "collector"
      reason: "Provides GitHub data that this policy evaluates"
  
  # Optional cross-linking
  related:
    - slug: "vcs"
      type: "policy"
      reason: "Enforces branch protection and merge strategy standards"
```

**Additional fields per type:**

| Type | Additional Fields |
|------|------------------|
| Collectors | `example_component_json`, `inputs`, `secrets` |
| Policies | `inputs`, `requires` (required) |
| Catalogers | `example_catalog_json`, `inputs`, `secrets` |

**Sub-component arrays** (e.g., `collectors:`, `policies:`, `catalogers:`) include:
- `name`: Identifier for the sub-component
- `description`: What it collects/enforces/syncs
- `keywords`: SEO keywords array (required)
- `hook`: Trigger configuration (type, schedule, pattern)

### Status Badges

| Status | Badge Color | Description |
|--------|-------------|-------------|
| `stable` | Green | Production ready, well tested, recommended for use |
| `beta` | Blue | Feature complete, may have minor issues, API stable |
| `experimental` | Amber | Early development, API may change, use with caution |
| `deprecated` | Red | No longer recommended, will be removed in future |

### Current Implementation State

The following has been implemented:
- All YAML metadata populated for collectors, policies, and catalogers
- Nightly sync pipeline (`+update-lunar-lib`)
- Individual detail pages for collectors, policies, and catalogers
- Index page at `/lunar/guardrails/` (to be restructured)
- Collectors list page at `/lunar/guardrails/collectors/` (to be removed)
- Category filtering on collectors list page
- CSS styling (guardrails.css, plugin.css, collectors.css, etc.)
- SEO basics (meta tags, JSON-LD structured data)

---

## Problem Statement

The current implementation exposes too many concepts at once on the index page (`/lunar/guardrails/`):

- **Guardrails** (umbrella term)
- **Collectors** (data gathering layer)
- **Policies** (enforcement layer)
- **Catalogers** (metadata sync layer)
- **Plugins** (reusable modules)

Feedback indicates this is overwhelming. Users struggle to understand the relationship between these concepts and which ones matter for their use case.

**Goal:** Simplify the mental model by reorganizing into two primary entry points:
1. **Integrations** — How Lunar connects to your tools (collectors + catalogers)
2. **Guardrails** — What Lunar enforces (policies containing individual guardrails)

---

## Terminology Changes

### Old vs New Terminology

| Context | Old Term | New Term | Notes |
|---------|----------|----------|-------|
| Umbrella for collectors + catalogers | (none) | **Integration** | New umbrella concept |
| Individual pass/fail check | sub-policy | **Guardrail** | User-facing term for what gets enforced |
| Container of guardrails | policy plugin | **Policy** | Groups related guardrails |
| Data gathering script | collector | **Collector** (under Integrations) | Unchanged, just reorganized |
| Metadata sync script | cataloger | **Cataloger** (under Integrations) | Unchanged, just reorganized |
| Reusable module | plugin | *(avoid)* | Don't use "plugin" in marketing copy |

### Terminology Guidelines

- **Never use "plugin"** on the marketing website — it's an internal implementation detail
- **"Guardrail"** is the primary user-facing concept — it's what users care about ("I want to enforce X")
- **"Policy"** is a logical grouping of related guardrails (e.g., "VCS Policies" contains branch protection, merge strategy, and other VCS-related guardrails)
- **"Integration"** emphasizes the connection to external tools — it's technology-focused

### Display Name Suffix Changes

| Type | Old Suffix | New Suffix |
|------|-----------|------------|
| Collector | "Collector" | "Collector" *(unchanged)* |
| Cataloger | "Cataloger" | "Cataloger" *(unchanged)* |
| Policy | "Policies" | "Guardrails" (e.g., "VCS Guardrails") |

**lunar-lib validation script updates:**
- Collectors: `display_name` must end with "Collector" *(unchanged)*
- Catalogers: `display_name` must end with "Cataloger" *(unchanged)*
- Policies: `display_name` must end with "Guardrails" (e.g., "Container Guardrails")

---

## URL Structure

### New Structure

```
/lunar/integrations/                           # Index page for all integrations
/lunar/integrations/collectors/                # Redirect → /lunar/integrations/
/lunar/integrations/catalogers/                # Redirect → /lunar/integrations/
/lunar/integrations/collectors/{slug}/         # Individual collector page
/lunar/integrations/catalogers/{slug}/         # Individual cataloger page

/lunar/guardrails/                             # Index page for all guardrails
/lunar/guardrails/{policy-slug}/               # Individual policy page (contains multiple guardrails)
/lunar/guardrails/{policy-slug}/{guardrail}/   # Individual guardrail page (Phase 6)
  ?collector={collector-slug}                  # Optional: specific collector use-case
```

### Redirects

Since v1 hasn't shipped to production, no legacy redirect map is needed. The following redirects consolidate index pages:

| From | To | Reason |
|------|-----|--------|
| `/lunar/integrations/collectors/` | `/lunar/integrations/` | No separate collectors index — use main integrations page |
| `/lunar/integrations/catalogers/` | `/lunar/integrations/` | No separate catalogers index — use main integrations page |

### Breadcrumb Updates

**Integrations pages:**
```
Lunar › Integrations › Collectors › GitHub
Lunar › Integrations › Catalogers › GitHub Org
```

**Guardrails pages:**
```
Lunar › Guardrails › VCS
Lunar › Guardrails › VCS › Branch Protection  (Phase 6)
```

---

## Page Structure Changes

### `/lunar/integrations/` (formerly `/lunar/guardrails/index.njk`)

**Content to keep from current index.njk:**
- Hero section with tech cloud visual background
- Main headline (adapt to "Integrations")
- "100+ Guardrails Out of the Box" messaging (adapt)
- "How It Works" flow diagram (simplify — see below)
- CTA buttons

**Content to change:**
- Remove the three-card grid (Collectors / Policies / Catalogers) — too many concepts
- Add combined collectors + catalogers grid with:
  - Type filter toggle: All | Collectors | Catalogers
  - Category filter bar (new technology-aligned categories — see [Categories](#categories))
- Reword all copy to use "Integrations" terminology
- Remove references to "plugins"
- Remove sub-collector/sub-cataloger counts (e.g., "6 plugins · 12 collectors") — just show integration count

**Flow diagram simplification:**
```
Current (4 steps):
1. Catalogers → 2. Collectors → 3. JSON → 4. Policies

New (2 steps):
1. Integrations gather data from your tools
2. Guardrails enforce your standards
```

### `/lunar/guardrails/` (new index page)

**Purpose:** Landing page for browsing guardrails (individual checks) and policies (guardrail groups).

**Key features:**
- Hero section explaining guardrails as enforceable standards
- **Client-side search** (Lunr.js or similar) — only for this page, not integrations
- Grid of policies, each showing:
  - Policy name (e.g., "VCS Guardrails")
  - Guardrail count (e.g., "5 guardrails")
  - Long description
  - Category badge
- **Expandable guardrails preview** — show first 3 guardrails inline, "Show all" to expand
- Category filter bar (keep existing 6 categories — these are verification-use-case aligned)

**Minimal integration mentions** — keep the page focused on "what can I enforce?" but add a CTA at the bottom:
> "Explore 30+ integrations that power Lunar's guardrail ecosystem →"

### `/lunar/integrations/collectors/{slug}/` (formerly `/lunar/guardrails/collectors/{slug}/`)

**Diagram changes:**
- Remove cataloger step from "How Collectors Fit into Lunar" diagram
- Simplify to 3 steps:
  1. Collectors gather SDLC data ← This page
  2. Centralized as JSON
  3. Guardrails enforce standards

**Terminology changes:**
- "Included Collectors" → "What This Integration Collects"
- "Related Plugins" → "Related Integrations" or "Related Guardrails"

### `/lunar/integrations/catalogers/{slug}/` (formerly `/lunar/guardrails/catalogers/{slug}/`)

**Diagram changes:**
- Collapse steps 2, 3, 4 into a single "Guardrails Engine" step:
  1. Catalogers sync context ← This page
  2. Guardrails Engine (collectors + guardrails work together on cataloged data)

**Subtext for step 2:**
> "Once cataloged, components are automatically analyzed by collectors and evaluated against your guardrails."

**Terminology changes:**
- "Included Catalogers" → "What This Integration Syncs"
- "Related Plugins" → "Related Integrations" or "Related Guardrails"

### `/lunar/guardrails/{policy-slug}/` (formerly `/lunar/guardrails/policies/{slug}/`)

**Diagram changes:**
- Remove cataloger step from "How Policies Fit into Lunar" diagram
- Simplify to 3 steps:
  1. Collectors gather data (link to integration)
  2. Centralized as JSON
  3. Guardrails enforce standards ← This page

**Terminology changes:**
- "Included Policies" → "Included Guardrails"
- "Policy" badge → "Guardrail Group" or just hide the badge
- "Related Plugins" → "Related Guardrails" or "Related Integrations"
- "Required Collectors" → "Required Integrations"
- Update display name suffix from "Policies" → "Guardrails"

### `/lunar/guardrails/{policy-slug}/{guardrail-slug}/` (Phase 6)

**New page for individual guardrails with optional collector context.**

**URL examples:**
- `/lunar/guardrails/vcs/branch-protection/` — Base guardrail page
- `/lunar/guardrails/vcs/branch-protection/?collector=github` — GitHub-specific use case

**Content:**
- Guardrail name and description
- What it checks (the assertion)
- Which integrations provide data for this guardrail
- Example pass/fail scenarios
- Configuration options
- Copy-paste YAML snippet for enabling this specific guardrail

**SEO benefit:** Captures long-tail searches like "enforce branch protection on github", "require code review before merge"

---

## Categories

### Integration Categories (Technology-Aligned)

New categories for collectors and catalogers, organized by technology rather than verification use case:

| Category Slug | Display Name | Example Integrations |
|--------------|--------------|---------------------|
| `vcs` | Version Control | GitHub, GitLab, Bitbucket |
| `ci-cd` | CI/CD | GitHub Actions, CircleCI, BuildKite, Jenkins |
| `build` | Build Tools | Maven, Gradle, Make, Bazel |
| `containers` | Containers | Docker, Podman, container registries |
| `orchestration` | Orchestration | Kubernetes, Helm, ArgoCD |
| `code-analysis` | Code Analysis | ast-grep, CodeQL, SonarQube |
| `testing` | Testing & Coverage | Codecov, Coveralls, Jest, pytest |
| `security` | Security Scanning | Trivy, Snyk, Dependabot |
| `languages` | Languages & Runtimes | Go, Python, Node.js, Java |
| `documentation` | Documentation | README detection, OpenAPI |
| `service-catalog` | Service Catalog | Backstage, OpsLevel, Cortex |

**Note:** A single integration can belong to multiple categories (e.g., Dockerfile collector → `categories: ["containers", "build"]`). Uses the same `categories` field as policies, but with different valid values.

### Policy/Guardrail Categories (Verification-Use-Case Aligned)

Keep existing 6 categories — these make sense for "what do I want to enforce?":

| Category Slug | Display Name |
|--------------|--------------|
| `repository-and-ownership` | Repository & Ownership |
| `deployment-and-infrastructure` | Deployment & Infrastructure |
| `testing-and-quality` | Testing & Quality |
| `devex-build-and-ci` | DevEx, Build & CI |
| `security-and-compliance` | Security & Compliance |
| `operational-readiness` | Operational Readiness |

---

## Implementation Phases

### Phase 1: Terminology Updates (lunar-lib) ✅ COMPLETE

**Validation script updates:**
- [x] Update `display_name` suffix requirements:
  - Collectors: must end with "Collector" *(unchanged)*
  - Catalogers: must end with "Cataloger" *(unchanged)*
  - Policies: must end with "Guardrails" *(new)*
- [x] Update `category` field to validate against different sets based on type:
  - Policies: verification use-case aligned (repository-and-ownership, testing-and-quality, etc.)
  - Collectors/Catalogers: technology-aligned (vcs, containers, build, languages, etc.)

**YAML file updates:**
- [x] Update all policy `display_name` values (e.g., "Container Policies" → "Container Guardrails")
- [x] Update all policy README titles to match new display_name
- [x] Update all collectors/catalogers to use `categories` with technology-aligned values

**README template updates:**
- [x] Update terminology in all templates
- [x] Remove "plugin" references

### Phase 2: URL Structure & Redirects (earthly-website)

**File renames:**
- [ ] `collectors.njk` → delete (functionality moves to integrations index)
- [ ] `collector.njk` → `src/lunar/integrations/collector.njk`
- [ ] `cataloger.njk` → `src/lunar/integrations/cataloger.njk`
- [ ] `index.njk` → `src/lunar/integrations/index.njk` (adapt content)
- [ ] `policy.njk` → `src/lunar/guardrails/policy.njk` (rename from policies/)
- [ ] Create new `src/lunar/guardrails/index.njk` (guardrails index page)

**Permalink updates:**
- [ ] Collector pages: `/lunar/integrations/collectors/{slug}/`
- [ ] Cataloger pages: `/lunar/integrations/catalogers/{slug}/`
- [ ] Policy pages: `/lunar/guardrails/{slug}/`

**Redirects (in netlify.toml or eleventy config):**
- [ ] `/lunar/integrations/collectors/` → `/lunar/integrations/`
- [ ] `/lunar/integrations/catalogers/` → `/lunar/integrations/`

### Phase 3: Integrations Index Page

**Create `/lunar/integrations/index.njk`:**
- [ ] Adapt hero section from old guardrails index
- [ ] Simplify "How It Works" to 2-step flow
- [ ] Combine collectors + catalogers into single grid
- [ ] Add type toggle filter: All | Collectors | Catalogers
- [ ] Add category filter bar with new technology-aligned categories
- [ ] Update all terminology (remove "plugin", use "integration")
- [ ] Remove sub-collector/sub-cataloger counts — just show integration count

### Phase 4: Guardrails Index Page

**Create `/lunar/guardrails/index.njk`:**
- [ ] New hero section focused on "what can I enforce?"
- [ ] Policy/guardrail grid with expandable guardrail previews
- [ ] Category filter bar (6 existing categories)
- [ ] **Client-side search** using Lunr.js or similar
  - Index policy names, guardrail names, descriptions, keywords
  - Real-time filtering as user types
- [ ] Add CTA at bottom linking to integrations page

### Phase 5: Diagram Simplifications

**Collector page (`collector.njk`):**
- [ ] Remove cataloger step from "How Collectors Fit" diagram
- [ ] Update to 3-step flow: Collectors → JSON → Guardrails

**Cataloger page (`cataloger.njk`):**
- [ ] Collapse steps 2-4 into single "Guardrails Engine" step
- [ ] Update to 2-step flow: Catalogers → Guardrails Engine
- [ ] Add subtext explaining collectors + guardrails work on cataloged data

**Policy page (`policy.njk`):**
- [ ] Remove cataloger step from "How Policies Fit" diagram
- [ ] Update to 3-step flow: Collectors → JSON → Guardrails
- [ ] Rename "Required Collectors" → "Required Integrations"

### Phase 6: Individual Guardrail Pages

**Create `/lunar/guardrails/{policy}/{guardrail}/`:**
- [ ] Design URL structure for guardrail + collector combinations
- [ ] Create paginated template for individual guardrail pages
- [ ] Add `?collector=` query param support for collector-specific context
- [ ] Show which integrations provide data for this guardrail
- [ ] Include copy-paste YAML configuration snippet
- [ ] Add cross-linking from parent policy pages
- [ ] Implement SEO for long-tail keywords

### Phase 7: SEO Metadata Review

Defer full SEO implementation until after structure is finalized. Initial implementation should include only:

- [ ] Basic meta description (from `long_description`)
- [ ] Basic meta keywords (from `keywords` arrays)
- [ ] Canonical URLs for all pages
- [ ] Basic Open Graph tags

**Full SEO implementation (later):**
- [ ] Review and update JSON-LD structured data for new URL structure
- [ ] Update BreadcrumbList schemas for new hierarchy
- [ ] Review SoftwareSourceCode schemas
- [ ] Update FAQPage schemas with new terminology
- [ ] Generate XML sitemap with new URLs
- [ ] Submit sitemap to search engines
- [ ] Set up URL monitoring in Google Search Console
- [ ] Review and update internal linking structure
