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

### Phase 2: URL Structure & Redirects (earthly-website) ✅ COMPLETE

**File renames:**
- [x] `collectors.njk` → delete (functionality moves to integrations index)
- [x] `collector.njk` → `src/lunar/integrations/collector.njk`
- [x] `cataloger.njk` → `src/lunar/integrations/cataloger.njk`
- [x] `index.njk` → `src/lunar/integrations/index.njk` (adapt content)
- [x] `policy.njk` stays at `src/lunar/guardrails/policy.njk` (was already there)
- [x] Create new `src/lunar/guardrails/index.njk` (guardrails index page placeholder)

**Permalink updates:**
- [x] Collector pages: `/lunar/integrations/collectors/{slug}/`
- [x] Cataloger pages: `/lunar/integrations/catalogers/{slug}/`
- [x] Policy pages: `/lunar/guardrails/{slug}/`

**Redirects (in netlify.toml):**
- [x] `/lunar/integrations/collectors/` → `/lunar/integrations/`
- [x] `/lunar/integrations/catalogers/` → `/lunar/integrations/`

### Phase 3: Integrations Index Page

**Create `/lunar/integrations/index.njk`:**
- [x] Adapt hero section from old guardrails index
- [x] Simplify "How It Works" to 2-step flow
- [x] Combine collectors + catalogers into single grid
- [x] Add type toggle filter: All | Collectors | Catalogers
- [x] Add category filter bar with new technology-aligned categories
- [x] Update all terminology (remove "plugin", use "integration")
- [x] Remove sub-collector/sub-cataloger counts — just show integration count

### Phase 4: Guardrails Index Page

**Create `/lunar/guardrails/index.njk`:**
- [x] New hero section focused on "what can I enforce?"
- [x] Policy/guardrail grid with expandable guardrail previews
- [x] Category filter bar (6 existing categories)
- [x] **Client-side search** (custom implementation with debounce)
  - Index policy names, guardrail names, descriptions, keywords
  - Real-time filtering as user types
- [x] Add CTA at bottom linking to integrations page

**Files modified:**
- `src/lunar/guardrails/index.njk` - Full template with search, filters, expandable previews
- `src/assets/js/lunar-plugin-index.js` - Extended to handle both integrations and guardrails pages
- `src/assets/css/lunar-plugin-index.css` - Extended with search, preview, and guardrails-specific styles

### Phase 5: Diagram Simplifications (DONE)

**Collector page (`collector.njk`):**
- [x] Remove cataloger step from "How Collectors Fit" diagram
- [x] Update to 3-step flow: Collectors → JSON → Guardrails
- [x] Update "Included Collectors" → "What This Integration Collects"
- [x] Update "Related Plugins" → "Related Integrations"
- [x] Fix related links to use new URL structure
- [x] Fix breadcrumb to show Integrations instead of Guardrails

**Cataloger page (`cataloger.njk`):**
- [x] Collapse steps 2-4 into single "Guardrails Engine" step
- [x] Update to 2-step flow: Catalogers → Guardrails Engine
- [x] Add subtext explaining collectors + guardrails work on cataloged data
- [x] Update "Included Catalogers" → "What This Integration Syncs"
- [x] Update "Related Plugins" → "Related Integrations"
- [x] Fix related links to use new URL structure

**Policy page (`policy.njk`):**
- [x] Remove cataloger step from "How Policies Fit" diagram
- [x] Update to 3-step flow: Integrations → JSON → Guardrails
- [x] Rename "Required Collectors" → "Required Integrations"
- [x] Update "Included Policies" → "Included Guardrails"
- [x] Update "Related Plugins" → "Related Guardrails"
- [x] Fix related and requires links to use new URL structure

### Phase 6: Individual Guardrail Pages ✅ COMPLETE

**Zapier-style combination pages implemented:**

The implementation follows Zapier's pattern (e.g., `/apps/fathom/integrations/gmail`) where each page combines two entities. In Lunar's case:
- **Guardrail + Collector** combinations (e.g., "Branch Protection + GitHub")

**URL Structure:**
- Base guardrail page: `/lunar/guardrails/{policy}/{guardrail}/` (hub with compatible integrations)
- Combination page: `/lunar/guardrails/{policy}/{guardrail}/{collector}/` (detailed combo page)

**Example URLs:**
- `/lunar/guardrails/vcs/branch-protection-enabled/` → Hub listing compatible collectors
- `/lunar/guardrails/vcs/branch-protection-enabled/github/` → Full combo page with GitHub Collector

**Checklist:**
- [x] Design URL structure for guardrail + collector combinations
- [x] Create paginated template for individual guardrail pages (`guardrail.njk`)
- [x] Create Zapier-style combination page template (`guardrail-collector.njk`)
- [x] Show "Compatible Integrations" on base guardrail page with links to combo pages
- [x] Include combined YAML configuration snippet (collector + policy)
- [x] Show data flow: Collector → Component JSON → Guardrail
- [x] Add cross-linking from parent policy pages
- [x] Implement SEO for long-tail keywords (e.g., "GitHub branch protection enforcement")

**Files created/modified:**
- `src/_data/guardrails.js`:
  - Added `individualGuardrails` array (base guardrail pages)
  - Added `guardrailCollectorCombos` array (combination pages)
  - Each combo includes full guardrail + collector data for template access
- `src/lunar/guardrails/guardrail.njk` - Base guardrail page (hub listing compatible integrations)
- `src/lunar/guardrails/guardrail-collector.njk` - Zapier-style combination page
- `src/lunar/guardrails/policy.njk` - Updated to link to individual guardrail pages
- `src/lunar/guardrails/index.njk` - Updated guardrail links to point to individual pages
- `src/assets/css/lunar-plugin-detail.css`:
  - Added `.compatible-integrations-section` styles (hub page)
  - Added `.combo-*` styles (combination page: dual icons, flow diagram, etc.)

### Phase 7: SEO Metadata Review

#### Current State Summary

The base template (`base.njk`) provides default SEO metadata:
- Title, meta description, canonical URL, Open Graph, Twitter Cards
- Organization and WebSite JSON-LD schemas

Dynamic plugin pages (policies, guardrails, collectors, catalogers) have:
- Meta keywords, robots, author/publisher tags
- Inline microdata for SoftwareSourceCode and BreadcrumbList
- TODO comments for JSON-LD conversion

Static pages mostly rely on base template defaults and are missing page-specific SEO.

---

#### 7.1 Homepage (`/`)

**File:** `src/index.html`

- [x] Add `canonical_url: "https://earthly.dev/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/"` to frontmatter
- [x] Add custom `meta_description` (currently uses default)
- [x] Add JSON-LD WebPage schema with mainEntity pointing to Product
- [x] Add JSON-LD SoftwareApplication schema for Earthly Lunar (with featureList)
- [x] Internal links verified: CTAs point to /book-demo/, /how-lunar-works/, etc.

---

#### 7.2 About Page (`/about/`)

**File:** `src/about.html`

- [x] Add `canonical_url: "https://earthly.dev/about/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/about/"` to frontmatter
- [x] Add custom `meta_description` summarizing company mission
- [x] Add JSON-LD AboutPage schema
- [x] Add JSON-LD Organization schema (extended from base)
- [x] Internal links verified: uses standard CTA patterns

---

#### 7.3 How Lunar Works (`/how-lunar-works/`)

**File:** `src/how-lunar-works.html`

- [x] Add `canonical_url: "https://earthly.dev/how-lunar-works/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/how-lunar-works/"` to frontmatter
- [x] Add custom `meta_description` explaining Lunar's guardrails engine
- [x] Add JSON-LD WebPage schema with BreadcrumbList
- [x] Add JSON-LD HowTo schema for the step-by-step explanation (Instrument → Normalize → Evaluate → Enforce)
- [x] Internal links verified: uses standard CTA patterns

---

#### 7.4 Book Demo (`/book-demo/`)

**File:** `src/book-demo.html`

- [x] Add `canonical_url: "https://earthly.dev/book-demo/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/book-demo/"` to frontmatter
- [x] Add custom `meta_description` for demo booking (enhanced existing)
- [x] Add JSON-LD ContactPage schema with Product mainEntity and BreadcrumbList
- [x] Form uses HubSpot embed with standard accessibility (managed by HubSpot)

---

#### 7.5 Security (`/security/`)

**File:** `src/security.html`

- [x] Add `canonical_url: "https://earthly.dev/security/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/security/"` to frontmatter
- [x] Update frontmatter to use `meta_description` instead of `description`
- [x] Add JSON-LD WebPage schema with BreadcrumbList and SOC 2 credential
- [x] Update title (removed "Better SDLC", now "Security | Earthly")

---

#### 7.6 Earthfile Page (`/earthfile/`)

**File:** `src/earthfile.html`

- [x] Add `canonical_url: "https://earthly.dev/earthfile/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/earthfile/"` to frontmatter
- [x] Add custom `meta_description` for Earthfile product
- [x] Add JSON-LD SoftwareApplication schema for Earthfile (with featureList, downloadUrl, license)
- [x] Updated title to "Earthfiles - Fast, Consistent Builds | Earthly"
- [x] Earthfile page: keeping as-is (low prominence, not deprecated)

---

#### 7.7 Lunar and OPA (`/lunar-and-opa/`)

**File:** `src/lunar-and-opa.html`

- [x] Add `canonical_url: "https://earthly.dev/lunar-and-opa/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/lunar-and-opa/"` to frontmatter
- [x] Add custom `meta_description` for Lunar vs OPA comparison
- [x] Add JSON-LD BreadcrumbList schema (FAQPage schema already existed)
- [x] Updated title to "Earthly Lunar + OPA - Better Together | Policy Enforcement"
- [x] Internal links verified: uses standard CTA patterns

---

#### 7.8 Newsroom (`/newsroom/`)

**File:** `src/newsroom.html`

- [x] Add `canonical_url: "https://earthly.dev/newsroom/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/newsroom/"` to frontmatter
- [x] Add custom `meta_description` for press/news section
- [x] Add JSON-LD CollectionPage schema with BreadcrumbList
- [x] Updated title to "Newsroom | Earthly" (removed "Better SDLC")
- [x] Added `rel="noopener noreferrer"` to all external links

---

#### 7.9 Legal Pages

##### 7.9.1 Terms of Service (`/tos/`)

**File:** `src/tos.html`

- [x] Add `canonical_url: "https://earthly.dev/tos/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/tos/"` to frontmatter
- [x] Add custom `meta_description`
- [x] Updated title to "Terms of Service | Earthly"
- [x] Verified: no robots meta = defaults to indexable (appropriate for legal pages)

##### 7.9.2 Privacy Policy (`/privacy-policy/`)

**File:** `src/privacy-policy.html`

- [x] Add `canonical_url: "https://earthly.dev/privacy-policy/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/privacy-policy/"` to frontmatter
- [x] Add custom `meta_description`
- [x] Updated title to "Privacy Policy | Earthly"
- [x] Verified: no robots meta = defaults to indexable

##### 7.9.3 Acceptable Use Policy (`/acceptable-use-policy/`)

**File:** `src/acceptable-use-policy.html`

- [x] Add `canonical_url: "https://earthly.dev/acceptable-use-policy/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/acceptable-use-policy/"` to frontmatter
- [x] Add custom `meta_description`
- [x] Updated title to "Acceptable Use Policy | Earthly"
- [x] Verified: no robots meta = defaults to indexable

##### 7.9.4 API Terms (`/api-terms/`)

**File:** `src/api-terms.html`

- [x] Add `canonical_url: "https://earthly.dev/api-terms/"` to frontmatter
- [x] Add `og_url: "https://earthly.dev/api-terms/"` to frontmatter
- [x] Add custom `meta_description`
- [x] Updated title to "API Terms | Earthly"
- [x] Verified: no robots meta = defaults to indexable

---

#### 7.10 Guardrails Index (`/lunar/guardrails/`)

**File:** `src/lunar/guardrails/index.njk`

- [x] Remove TODO comment
- [x] Add JSON-LD CollectionPage schema
- [x] Add JSON-LD BreadcrumbList schema (Lunar → Guardrails)
- [x] Verify all policy cards link to correct URLs
- [x] Review category filter functionality and accessibility
- [x] Meta keywords aggregation not needed (index has focused meta_description + CollectionPage schema)

---

#### 7.11 Policy Pages (`/lunar/guardrails/{policy-slug}/`)

**File:** `src/lunar/guardrails/policy.njk`

- [x] Add JSON-LD SoftwareSourceCode schema (via eleventyComputed.extraHeadContent)
- [x] Add JSON-LD BreadcrumbList schema (3-level: Lunar → Guardrails → Policy)
- [x] Move robots/author meta tags to extraHeadContent
- [x] Add JSON-LD ItemList schema for included guardrails (dynamically generated)
- [x] Verify all guardrail links use correct URL structure
- [x] Add internal links to related policies (same category)

---

#### 7.12 Individual Guardrail Pages (`/lunar/guardrails/{policy-slug}/{guardrail-slug}/`)

**File:** `src/lunar/guardrails/guardrail.njk`

- [x] Add JSON-LD SoftwareSourceCode schema (via eleventyComputed.extraHeadContent)
- [x] Add JSON-LD BreadcrumbList schema (4-level: Lunar → Guardrails → Policy → Guardrail)
- [x] Move robots/author meta tags to extraHeadContent
- [x] Add JSON-LD ItemList schema for compatible integrations (dynamically generated)
- [x] Verify all collector links use correct URL structure
- [x] Add internal links to sibling guardrails (same policy)

---

#### 7.13 Guardrail + Collector Combo Pages (`/lunar/guardrails/{policy-slug}/{guardrail-slug}/{collector-slug}/`)

**File:** `src/lunar/guardrails/guardrail-collector.njk`

- [x] Add JSON-LD HowTo schema for configuration steps (via eleventyComputed.extraHeadContent)
- [x] Add JSON-LD BreadcrumbList schema (5-level: Lunar → Guardrails → Policy → Guardrail → Collector)
- [x] Move robots/author meta tags to extraHeadContent
- [x] Verify back-links to parent guardrail and collector pages
- [x] Add internal links to other combos for same guardrail

---

#### 7.14 Integrations Index (`/lunar/integrations/`)

**File:** `src/lunar/integrations/index.njk`

- [x] Remove TODO comment
- [x] Add JSON-LD CollectionPage schema
- [x] Add JSON-LD BreadcrumbList schema (Lunar → Integrations)
- [x] Verify all collector/cataloger cards link to correct URLs
- [x] Review category filter functionality and accessibility
- [x] Add cross-link to guardrails index

---

#### 7.15 Collector Pages (`/lunar/integrations/collectors/{collector-slug}/`)

**File:** `src/lunar/integrations/collector.njk`

- [x] Remove TODO comment
- [x] Add JSON-LD SoftwareSourceCode schema (via eleventyComputed.extraHeadContent)
- [x] Add JSON-LD BreadcrumbList schema (3-level: Lunar → Integrations → Collector)
- [x] Move robots/author meta tags to extraHeadContent
- [x] Add JSON-LD ItemList schema for included sub-collectors (dynamically generated)
- [x] Add internal links to related collectors (same category)
- [x] Add internal links to guardrails that use this collector

---

#### 7.16 Cataloger Pages (`/lunar/integrations/catalogers/{cataloger-slug}/`)

**File:** `src/lunar/integrations/cataloger.njk`

- [x] Remove TODO comment
- [x] Add JSON-LD SoftwareSourceCode schema (via eleventyComputed.extraHeadContent)
- [x] Add JSON-LD BreadcrumbList schema (3-level: Lunar → Integrations → Cataloger)
- [x] Move robots/author meta tags to extraHeadContent
- [x] Add JSON-LD ItemList schema for included sub-catalogers (dynamically generated)
- [x] Add internal links to related catalogers (same category)

---

#### 7.17 Error Page (`/404.html`)

**File:** `src/404.html`

- [x] Add noindex meta tag (via extraHeadContent)
- [x] Add helpful internal links (How Lunar Works, Guardrails, Integrations, Docs)
- [x] Ensure consistent branding (uses gradient 404, standard buttons, site nav links)

---

#### 7.18 SEO Infrastructure Files

##### 7.18.1 Robots.txt

**File:** `src/robots.njk`

- [x] Verify sitemap URL is correct (https://earthly.dev/sitemap.xml)
- [x] Review disallow rules (only /automate-your-process/)
- [x] Verified `/automate-your-process/` is disallowed

##### 7.18.2 Sitemap Index

**File:** `src/sitemap.njk`

- [x] Verified sitemap index includes sitemap-pages.xml and blog sitemap
- [x] Sitemap index structure is correct (no lastmod needed at index level)
- [x] Priority values added to sitemap-pages.njk (see below)

##### 7.18.3 Sitemap Pages

**File:** `src/sitemap-pages.njk`

- [x] Dynamic pages included via collections.all (policies, guardrails, collectors, catalogers, combos)
- [x] Added changefreq values by page type (weekly for index, monthly for detail, yearly for legal)
- [x] Added priority values (1.0 homepage, 0.9 indexes, 0.7 plugin pages, 0.3 legal)
- [x] Excluded 404.html from sitemap

---

#### 7.19 Cross-Cutting Tasks

##### Meta Tags Placement Fix

- [x] Moved robots/author meta tags to `eleventyComputed.extraHeadContent` in all dynamic templates
  - `policy.njk` ✓
  - `guardrail.njk` ✓
  - `guardrail-collector.njk` ✓
  - `collector.njk` ✓
  - `cataloger.njk` ✓
- Note: Original meta keywords blocks (article:tag etc.) remain in body but are low priority; main SEO tags are now in head

##### Internal Linking Audit

- [x] Policy pages link to parent guardrails index (via breadcrumb)
- [x] Guardrail pages link to parent policy (via breadcrumb and "View All" button)
- [x] Guardrail pages link to sibling guardrails (via "Related Guardrails" section)
- [x] Combo pages link to parent guardrail and collector (via breadcrumb)
- [x] Collector pages link to guardrails via "Used By" section (where applicable)
- [x] Add "Related" sections on index pages for cross-category discovery (future enhancement)
- [ ] **Pre-deploy**: Run broken link checker (manual step, recommend `npx broken-link-checker`)

##### JSON-LD Template Patterns

- [x] Added JSON-LD schemas inline in templates (simpler than partials for this use case)
  - BreadcrumbList: all pages
  - SoftwareSourceCode: plugin detail pages
  - CollectionPage: index pages
  - ItemList: for sub-items on detail pages
  - HowTo: combo pages
- [x] Document JSON-LD patterns in AGENTS.md (added SEO Requirements section with schema table)

---

#### Phase 7 Completion Criteria

- [x] All pages have explicit canonical_url and og_url
- [x] All pages have custom meta_description (no defaults)
- [x] All dynamic pages have JSON-LD schemas (SoftwareSourceCode, BreadcrumbList, ItemList, HowTo)
- [x] Core meta tags (robots, author) moved to `<head>` via extraHeadContent
- [x] No TODO comments remain in templates
- [x] Internal linking via breadcrumbs and related sections
- [x] Sitemap includes all pages with priority and changefreq
- [x] Robots.txt verified accurate

**Phase 7 Status: COMPLETE** ✓
