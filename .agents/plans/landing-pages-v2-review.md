# Landing Pages v2 - Implementation Review

**Review Date:** 2026-01-30  
**Plan Location:** `lunar-lib/.agents/plans/landing-pages-v2.md`

---

## Executive Summary

The Landing Pages v2 implementation is **substantially complete** with all 7 phases marked as done. The implementation successfully achieves the primary goals:

- ✅ Simplified terminology (Integrations + Guardrails)
- ✅ New URL structure with proper redirects
- ✅ Individual guardrail pages with Zapier-style combos (Phase 6)
- ✅ Comprehensive SEO metadata (Phase 7)
- ✅ Cross-linking between related pages

**Overall Grade: A**

All significant issues have been addressed. Only cosmetic items remain (internal filenames).

---

## Phase-by-Phase Assessment

### Phase 1: Terminology Updates (lunar-lib) — ✅ Complete with 1 issue

| Item | Status | Notes |
|------|--------|-------|
| Policy `display_name` suffix validation | ✅ | Must end with "Guardrails" |
| Policy YAML files updated | ✅ | All 6 policies use "Guardrails" suffix |
| Collector/Cataloger categories | ✅ | All use technology-aligned values |
| README templates updated | ✅ | Templates use "Guardrails" terminology |

**Issue Found:**
- `validate_readme_structure.py` line 58 has `"title_suffix": "Policies"` but should be `"Guardrails"` to match the YAML `display_name` values and README template

---

### Phase 2: URL Structure & Redirects — ✅ Complete

| Item | Status |
|------|--------|
| Collector pages at `/lunar/integrations/collectors/{slug}/` | ✅ |
| Cataloger pages at `/lunar/integrations/catalogers/{slug}/` | ✅ |
| Policy pages at `/lunar/guardrails/{slug}/` | ✅ |
| Redirect: `/lunar/integrations/collectors/` → `/lunar/integrations/` | ✅ |
| Redirect: `/lunar/integrations/catalogers/` → `/lunar/integrations/` | ✅ |

No issues found. Redirects configured correctly in `netlify.toml` with 301 status.

---

### Phase 3: Integrations Index Page — ✅ Complete

| Item | Status |
|------|--------|
| Hero section | ✅ |
| 2-step flow diagram | ✅ |
| Combined collectors + catalogers grid | ✅ |
| Type toggle filter (All/Collectors/Catalogers) | ✅ |
| Category filter bar (technology-aligned) | ✅ |
| JSON-LD schemas (CollectionPage, BreadcrumbList) | ✅ |
| "Integration" terminology (no "plugin") | ✅ |

**Minor Observation:**
- CSS/JS filenames still use "plugin" (`lunar-plugin-index.css`, `lunar-plugin-index.js`) but content uses "integration" terminology. This is cosmetic and doesn't affect functionality.

---

### Phase 4: Guardrails Index Page — ✅ Complete with observations

| Item | Status | Notes |
|------|--------|-------|
| Hero section | ✅ | Emphasizes quantity ("100+ Guardrails Out of the Box") |
| Policy/guardrail grid | ⚠️ | Uses split-view layout instead of expandable previews |
| Category filter bar | ✅ | All 6 categories present |
| Client-side search | ✅ | Debounced search implemented |
| Links to individual guardrail pages | ✅ | Correct URL format |
| JSON-LD schemas | ✅ | CollectionPage + BreadcrumbList |
| CTA linking to integrations | ⚠️ | Bottom CTA links to demo, not integrations |

**Observations:**
1. The grid uses a split-view layout (policies left, guardrails right) rather than expandable preview cards. CSS for expandable previews exists but isn't used. The current layout works but differs from the plan.
2. The hero emphasizes quantity rather than "what can I enforce?" messaging
3. The bottom CTA section uses the standard demo CTA rather than linking to integrations. However, integrations links exist in the hero and "How It Works" sections.

These are design choices rather than bugs — the page is functional.

---

### Phase 5: Diagram Simplifications — ✅ Complete

| Template | Diagram | Status |
|----------|---------|--------|
| `collector.njk` | 3-step: Collectors → JSON → Guardrails | ✅ |
| `cataloger.njk` | 2-step: Catalogers → Guardrails Engine | ✅ |
| `policy.njk` | 3-step: Integrations → JSON → Guardrails | ✅ |

All diagrams correctly simplified per the plan.

---

### Phase 6: Individual Guardrail Pages — ✅ Complete with 1 minor issue

| Item | Status |
|------|--------|
| `guardrail.njk` — base hub page | ✅ |
| `guardrail-collector.njk` — Zapier-style combo | ✅ |
| `guardrails.js` generates `individualGuardrails` | ✅ |
| `guardrails.js` generates `guardrailCollectorCombos` | ✅ |
| Compatible integrations list | ✅ |
| Combined YAML snippets | ✅ |
| Data flow diagram | ✅ |
| JSON-LD schemas | ⚠️ |
| CSS combo-* styles | ✅ |

**Issue Found:**
- `guardrail-collector.njk` is missing an `ItemList` schema for the sub-collectors section (lines 293-326). The individual guardrail page has this schema, but the combo page does not.

---

### Phase 7: SEO Metadata — ✅ Complete with 2 minor issues

| Page Type | Status |
|-----------|--------|
| Homepage | ✅ |
| About | ✅ |
| How Lunar Works | ✅ |
| Book Demo | ✅ |
| Security | ✅ |
| Earthfile | ✅ |
| Lunar and OPA | ✅ |
| Newsroom | ✅ |
| Legal pages (ToS, Privacy, etc.) | ✅ |
| Guardrails Index | ✅ |
| Policy pages | ⚠️ |
| Individual guardrail pages | ✅ |
| Combo pages | ✅ |
| Integrations Index | ✅ |
| Collector pages | ⚠️ |
| Cataloger pages | ⚠️ |
| 404 page | ✅ |
| Sitemap | ✅ |
| Robots.txt | ✅ |

**Issues Found:**

1. **Breadcrumb mismatch in collector/cataloger pages:**
   - HTML breadcrumbs show 4 levels: `Lunar → Integrations → Collectors → DisplayName`
   - JSON-LD BreadcrumbList only shows 3 levels: `Lunar → Integrations → DisplayName`
   - The "Collectors"/"Catalogers" level is missing from JSON-LD schema

2. **Policy page "Related" section heading:**
   - Line 393: Uses `<h2>Related</h2>` but should be `<h2>Related Guardrails</h2>` for consistency with `guardrail.njk`

---

## Issues Summary

### Priority 1 (Should Fix) — ✅ ALL FIXED

| # | Location | Issue | Status |
|---|----------|-------|--------|
| 1 | `lunar-lib/scripts/validate_readme_structure.py:58` | Policies validation expects "Policies" suffix but should expect "Guardrails" | ✅ Fixed |
| 2 | `earthly-website/src/lunar/integrations/collector.njk` | JSON-LD BreadcrumbList missing "Collectors" level | ✅ Fixed |
| 3 | `earthly-website/src/lunar/integrations/cataloger.njk` | JSON-LD BreadcrumbList missing "Catalogers" level | ✅ Fixed |

### Priority 2 (Nice to Have)

| # | Location | Issue | Status |
|---|----------|-------|--------|
| 4 | `earthly-website/src/lunar/guardrails/policy.njk:393` | Section heading is "Related" instead of "Related Guardrails" | ⏭️ Won't fix (by design) |
| 5 | `earthly-website/src/lunar/guardrails/guardrail-collector.njk` | Missing ItemList schema for sub-collectors | ✅ Fixed |

### Priority 3 (Optional/Cosmetic)

| # | Location | Issue | Notes |
|---|----------|-------|-------|
| 6 | CSS/JS filenames | Still use "plugin" (`lunar-plugin-*.css/js`) | Content uses "integration"; filenames are internal only |
| 7 | JS comment | `lunar-plugin-index.js` line 2 says "plugin" | Comment only, no user impact |

---

## Outstanding Pre-Deploy Tasks

From the plan, one task remains incomplete:

- [ ] **Run broken link checker** — Recommended: `npx broken-link-checker https://localhost:8080 --recursive`

---

## Recommendations

### Immediate (Before Deploy) — ✅ DONE

1. ~~**Fix validation script mismatch** (Priority 1, #1)~~ ✅ Fixed
2. ~~**Fix BreadcrumbList schemas** (Priority 1, #2-3)~~ ✅ Fixed

### Post-Deploy Enhancements

1. Consider adding the ItemList schema to combo pages for better structured data coverage

2. The guardrails index page uses a split-view layout instead of expandable previews. If the expandable preview UX is preferred, the CSS is already in place — just needs template changes.

3. Run a broken link check before going live

---

## What Went Well

1. **Comprehensive JSON-LD implementation** — All page types have appropriate schema types (SoftwareSourceCode, CollectionPage, HowTo, BreadcrumbList, ItemList)

2. **Clean URL structure** — Intuitive paths like `/lunar/guardrails/vcs/branch-protection-enabled/github/` are SEO-friendly and human-readable

3. **Terminology consistency** — "Integration" and "Guardrails" used consistently across user-facing content

4. **Zapier-style combo pages** — Innovative approach for long-tail SEO targeting specific guardrail + collector combinations

5. **Complete sitemap with priorities** — Different priority values for homepage (1.0), indexes (0.9), plugin pages (0.7), and legal (0.3)

6. **Proper redirects** — 301 redirects for consolidated index pages

---

## Files Modified Summary

### earthly-website

| Directory | Files |
|-----------|-------|
| `src/lunar/guardrails/` | `index.njk`, `policy.njk`, `guardrail.njk`, `guardrail-collector.njk` |
| `src/lunar/integrations/` | `index.njk`, `collector.njk`, `cataloger.njk` |
| `src/` | `index.html`, `about.html`, `how-lunar-works.html`, `book-demo.html`, `security.html`, `earthfile.html`, `lunar-and-opa.html`, `newsroom.html`, `tos.html`, `privacy-policy.html`, `acceptable-use-policy.html`, `api-terms.html`, `404.html`, `sitemap-pages.njk`, `robots.njk` |
| `src/_data/` | `guardrails.js` |
| `src/assets/css/` | `lunar-plugin-index.css`, `lunar-plugin-detail.css` |
| `src/assets/js/` | `lunar-plugin-index.js`, `lunar-plugin-detail.js` |
| Root | `netlify.toml` |

### lunar-lib

| Directory | Files |
|-----------|-------|
| `policies/*/` | `lunar-policy.yml`, `README.md` |
| `collectors/*/` | `lunar-collector.yml` |
| `catalogers/*/` | `lunar-cataloger.yml` |
| `scripts/` | `validate_landing_page_metadata.py`, `validate_readme_structure.py` |
| `ai-context/` | Template files |

---

## Conclusion

The implementation is production-ready. All Priority 1 issues have been fixed. The architecture is sound, SEO is comprehensive, and the user experience has been simplified from 5 concepts to 2 clear entry points (Integrations and Guardrails).

**Recommendation:** Run broken link checker, then deploy.
