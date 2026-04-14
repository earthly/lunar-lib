# Design: Importable Topic-Based Packs

> Discussion document for Brandon & Vlad — not a final spec.
> Explores what importable packs would look like if built around topics
> instead of monolithic starter configs.

## Problem

The current starter packs (PR #121) are copy-paste configs. Vlad wants the
platform to support a single `uses:` import for a combined collector+policy
package. Brandon wants packs organized by topic rather than by complexity tier.

Both are right — but the details matter. This doc explores the design space.

## Core Idea: Topic Packs

Instead of monolithic "starter" configs that try to cover everything, packs are
organized by topic. Each pack owns a cohesive domain and tries not to overlap
with other packs.

**Proposed packs:**

| Pack | Domain | Example contents |
|------|--------|-----------------|
| `baseline` | Repo hygiene, languages, testing | repo-boilerplate, testing, linter, all language policies |
| `security` | Vulnerability scanning, secrets, supply chain | secrets, sca, sast, container-scan, sbom |
| `iac` | Infrastructure as code | k8s, terraform, docker, container, github-actions, ci |
| `ai` | AI development practices | ai, claude, codex, gemini, coderabbit |
| `soc2` | SOC2 / compliance | vcs (branch protection, approvals), audit trail, access controls |

Users import the packs that match their needs:

```yaml
packs:
  - uses: github://earthly/lunar-lib/packs/baseline@v1
  - uses: github://earthly/lunar-lib/packs/security@v1
  - uses: github://earthly/lunar-lib/packs/ai@v1
```

## Pack Manifest Format

Each pack is a directory with a manifest declaring its collectors and policies.
This is essentially the current `lunar-config.yml` format, wrapped in an
importable package:

```yaml
# packs/security/pack.yml
name: security
version: 1.0.0
description: Vulnerability scanning, secret detection, supply-chain security

requires:
  secrets:
    - SNYK_TOKEN  # optional — sca works without it but Snyk won't run

collectors:
  - uses: github://earthly/lunar-lib/collectors/gitleaks@v1.0.5
  - uses: github://earthly/lunar-lib/collectors/trivy@v1.0.5
  - uses: github://earthly/lunar-lib/collectors/syft@v1.0.5
  - uses: github://earthly/lunar-lib/collectors/semgrep@v1.0.5
  - uses: github://earthly/lunar-lib/collectors/codeql@v1.0.5

policies:
  - uses: github://earthly/lunar-lib/policies/secrets@main
    enforcement: block-pr
    include:
      - no-hardcoded-secrets

  - uses: github://earthly/lunar-lib/policies/secrets@main
    enforcement: score
    include:
      - executed

  - uses: github://earthly/lunar-lib/policies/sca@v1.0.5
    enforcement: score
    include:
      - executed
      - max-severity
    with:
      min_severity: "critical"

  - uses: github://earthly/lunar-lib/policies/sast@v1.0.5
    enforcement: score
    include:
      - executed
      - max-severity
    with:
      min_severity: "high"

  - uses: github://earthly/lunar-lib/policies/container-scan@v1.0.5
    enforcement: score
    include:
      - executed
      - max-severity
    with:
      min_severity: "critical"

  - uses: github://earthly/lunar-lib/policies/sbom@v1.0.5
    enforcement: score
    include:
      - sbom-exists
      - has-licenses
```

The manifest format is identical to `lunar-config.yml` with added metadata
(`name`, `version`, `description`, `requires`). Existing starter pack configs
would migrate to this format with minimal changes.

## Customization: Include / Exclude

Users customize packs without ejecting by using `exclude` and `with` on the
pack import:

### Excluding whole policies

```yaml
packs:
  - uses: packs/security@v1
    exclude:
      - container-scan   # we don't use containers
      - sbom             # not relevant yet
```

The platform resolves the import, then drops any policy whose ref matches an
entry in `exclude`. Simple string match on the policy name (last segment of the
`uses:` path).

### Overriding policy inputs

```yaml
packs:
  - uses: packs/security@v1
    with:
      sca.min_severity: "high"         # override sca default (was "critical")
      sast.min_severity: "critical"    # tighten sast (was "high")
```

The `with` block uses `<policy-name>.<input>` as the key. The platform matches
the policy name and passes the input through. Only policies that accept `with:`
inputs are overridable this way.

### Overriding enforcement level

```yaml
packs:
  - uses: packs/security@v1
    enforce:
      secrets.no-hardcoded-secrets: report-pr   # soften from block-pr
      sca: block-pr                              # tighten from score
```

The `enforce` block uses `<policy-name>` or `<policy-name>.<subpolicy>` as keys.
Policy-level overrides apply to all subpolicies of that policy. Subpolicy-level
overrides take precedence over policy-level.

## Handling Duplicates

### Strategy 1: Avoid duplication by design

The primary strategy is to avoid policy duplication across packs entirely. This
is the core reason packs are organized by topic rather than by complexity tier
— each pack owns a cohesive domain and deliberately excludes policies that
belong to another pack.

For example, `baseline` does NOT include `secrets` because that's security's
domain. `security` does NOT include `testing` or `linter` because that's
baseline's domain. Each pack is targeted precisely so that users can combine
them freely without hitting conflicts:

| Policy | Owner pack | Deliberately excluded from |
|--------|-----------|---------------------------|
| secrets | security | baseline, ai, iac |
| sca, sast, sbom | security | baseline |
| container, container-scan | iac | security |
| k8s, terraform, ci | iac | (unique to iac) |
| vcs (branch protection) | soc2 | security, baseline |
| repo-boilerplate | baseline | security, iac |
| testing, linter | baseline | security, iac |
| language policies (go, java, ...) | baseline | security, iac |
| ai, claude, codex, gemini | ai | (unique to ai) |

With clean ownership, the basic packs (`baseline + security + iac + ai`) have
**zero policy overlap**. A user can import all four and never encounter a
conflict. This should cover day-1 through month-6 for most teams.

### Strategy 2: Pack dependencies for specialized packs

Once users move beyond the basic packs into more specialized ones (soc2,
PCI-DSS, HIPAA, PII), duplication becomes harder to avoid. A soc2 pack
naturally wants some of the same policies as the security pack — secret
detection, vulnerability scanning, access controls.

Rather than duplicating those policies, a specialized pack can **declare a
dependency on another pack**:

```yaml
# packs/soc2/pack.yml
name: soc2
version: 1.0.0
description: SOC2 compliance — access controls, audit trail, data protection
requires:
  packs:
    - security@v1     # soc2 builds on top of security

collectors:
  - uses: github://earthly/lunar-lib/collectors/github@v1.0.5

policies:
  # SOC2-specific: stricter branch protection and audit controls
  - uses: github://earthly/lunar-lib/policies/vcs@v1.0.5
    enforcement: block-pr
    include:
      - branch-protection-enabled
      - require-pull-request
      - minimum-approvals
      - require-codeowner-review
      - disallow-force-push

  # SOC2-specific: additional compliance checks
  # (future policies as they're built)
```

When a user imports `soc2`, the platform also pulls in `security` automatically.
The soc2 pack only declares the policies it adds beyond what security provides
— no duplication.

**User's config stays clean:**

```yaml
packs:
  - uses: packs/baseline@v1
  - uses: packs/soc2@v1          # automatically imports security
  - uses: packs/iac@v1
```

Three lines. The user gets baseline + security + soc2 + iac without knowing
that soc2 depends on security.

**Where this gets interesting:** What happens when `soc2` and a future `pii`
pack both depend on `security` but want different enforcement opinions?

```yaml
# soc2 wants secrets at block-pr (strict compliance)
# pii wants secrets at score (monitoring only, different compliance regime)
```

Options for handling this:

1. **Pack dependencies are additive, not opinionated.** The dependent pack
   (soc2) inherits security's collectors and policy defaults as-is. If soc2
   needs stricter enforcement, it declares an `enforce` override:
   ```yaml
   requires:
     packs:
       - security@v1
         enforce:
           secrets.no-hardcoded-secrets: block-pr
   ```

2. **The user resolves at import time.** If both soc2 and pii import security
   with conflicting enforcement overrides, validation flags it and the user
   picks which opinion wins via their own `enforce` block.

3. **Pack dependencies only pull in collectors.** The dependent pack gets
   security's scanners (gitleaks, trivy, etc.) but declares its own policy
   imports with its own enforcement levels. This avoids enforcement conflicts
   entirely — each pack fully owns its policy opinions.

Option 3 is probably the safest starting point. It solves the collector
duplication problem (which is the bulk of the overlap) while keeping policy
enforcement decisions explicit per pack.

### Strategy 3: User-driven resolution as fallback

For cases that clean ownership and pack dependencies don't cover, the user
resolves conflicts explicitly. The platform does NOT automatically pick a winner
when two packs import the same policy — it flags the conflict and tells the user
how to fix it.

**Why not auto-resolve?**

Auto-resolution (e.g., "highest enforcement wins") sounds clean but introduces
surprising behavior:

- Two packs import the same policy with different `with:` inputs. Which input
  wins? There's no obviously correct answer.
- Auto-resolution hides what's actually running. Users should know exactly which
  policies are active and at what enforcement level.
- Silent promotion from `score` to `block-pr` can break developer workflows
  without the user understanding why PRs are suddenly blocked.

> **Future idea:** Auto-resolution with enforcement promotion could work as an
> opt-in behavior (`resolve: highest-enforcement`) for users who explicitly want
> it. Not recommended as a default.

**Validation catches duplicates:**

Hub-on-pull validates the resolved config and reports conflicts with actionable
fix suggestions:

```
⚠ Policy conflict: secrets@main appears in both 'security' and 'soc2'
  - security: enforcement=block-pr, include=[no-hardcoded-secrets]
  - soc2: enforcement=score, include=[no-hardcoded-secrets, executed]

  To resolve, either:
  1. Exclude from one pack:
     packs:
       - uses: packs/soc2@v1
         exclude: [secrets]

  2. Exclude from both and import directly:
     packs:
       - uses: packs/security@v1
         exclude: [secrets]
       - uses: packs/soc2@v1
         exclude: [secrets]
     policies:
       - uses: policies/secrets@main
         enforcement: block-pr
         include: [no-hardcoded-secrets, executed]
```

**Local validation:**

Users can validate before pushing:

```bash
lunar config validate
```

Same validation logic as hub-on-pull, but runs locally. Catches conflicts
early so the PR check doesn't surprise them.

### Summary: Three layers of defense

1. **Avoid duplication by design** — basic packs have zero overlap through clean
   topic ownership. Covers day-1 through month-6 for most teams.
2. **Pack dependencies** — specialized packs inherit from basic packs instead of
   duplicating. Covers the soc2/pii/hipaa tier.
3. **User-driven resolution** — when all else fails, validation flags conflicts
   and the user resolves via exclude or direct import. Covers power users with
   sophisticated multi-pack setups.

## Collector Deduplication

Collectors are simpler than policies — they just gather data, with no
enforcement level or include/exclude semantics. When two packs declare the
same collector, it runs once. This is safe to auto-resolve because:

- Collectors have no configuration that could conflict
- Running a collector twice is wasteful but not harmful
- The dedup rule is trivial: same ref = same collector = run once

Language collectors (go, java, node, python, etc.) are included in every pack
that needs language detection. They only trigger when the language is detected,
so there's zero cost to deduplicating them.

## Concrete Examples

### Example 1: Small startup, day 1

```yaml
packs:
  - uses: github://earthly/lunar-lib/packs/baseline@v1
  - uses: github://earthly/lunar-lib/packs/security@v1
```

Two lines. Zero config. Gets repo hygiene, language detection, testing/linting
checks, plus vulnerability scanning and secret detection. No overlap because
baseline and security own different domains.

### Example 2: Adding AI practices

```yaml
packs:
  - uses: github://earthly/lunar-lib/packs/baseline@v1
  - uses: github://earthly/lunar-lib/packs/security@v1
  - uses: github://earthly/lunar-lib/packs/ai@v1
```

Three lines. Still zero overlap — AI pack only contains AI-specific policies.

### Example 3: Infrastructure team

```yaml
packs:
  - uses: github://earthly/lunar-lib/packs/baseline@v1
  - uses: github://earthly/lunar-lib/packs/security@v1
  - uses: github://earthly/lunar-lib/packs/iac@v1
    with:
      container.no-latest: report-pr  # stricter for container images
```

IAC adds k8s, terraform, docker checks. One override to tighten container
image tagging.

### Example 4: Compliance team, month 6

```yaml
packs:
  - uses: github://earthly/lunar-lib/packs/baseline@v1
  - uses: github://earthly/lunar-lib/packs/soc2@v1     # depends on security, pulls it in
  - uses: github://earthly/lunar-lib/packs/iac@v1
```

SOC2 pack declares `requires: [security@v1]`, so importing soc2 automatically
includes security's collectors and policies. User doesn't need to import
security separately — soc2 builds on it. No duplication, no manual excludes.

### Example 5: Two compliance packs with conflicting opinions

```yaml
packs:
  - uses: github://earthly/lunar-lib/packs/baseline@v1
  - uses: github://earthly/lunar-lib/packs/soc2@v1     # depends on security
  - uses: github://earthly/lunar-lib/packs/pii@v1      # also depends on security
```

Both soc2 and pii depend on security. If they both only inherit security's
collectors (option 3 from pack dependencies), there's no conflict — each pack
owns its own policy enforcement opinions. Security's collectors run once
(deduped), soc2 declares its policies, pii declares its policies.

If soc2 and pii DO have overlapping policies (e.g., both want `vcs` at different
enforcement levels), validation flags it and the user resolves:

```yaml
packs:
  - uses: github://earthly/lunar-lib/packs/baseline@v1
  - uses: github://earthly/lunar-lib/packs/soc2@v1
    exclude: [vcs]                    # let pii's vcs opinion win
  - uses: github://earthly/lunar-lib/packs/pii@v1
```

### Example 6: Power user, partially ejected

```yaml
packs:
  - uses: github://earthly/lunar-lib/packs/baseline@v1
  - uses: github://earthly/lunar-lib/packs/ai@v1

# Imported security pack policies individually for full control
policies:
  - uses: github://earthly/lunar-lib/policies/secrets@main
    enforcement: block-pr
    include:
      - no-hardcoded-secrets
      - executed           # both checks at block-pr

  - uses: github://earthly/lunar-lib/policies/sca@v1.0.5
    enforcement: block-pr
    include:
      - max-severity
    with:
      min_severity: "high"
```

User still imports baseline and AI as packs (no need for per-policy control
there) but manages security policies directly because they need custom
enforcement levels.

## Topic Pack Contents (Detailed)

### baseline

Repo hygiene, languages, testing, and linting. The "every repo should have
this" pack. Zero secrets required.

**Collectors:**
- All 11 language collectors (go, java, nodejs, python, rust, php, cpp, dotnet, html, shell, ruby)
- repo-boilerplate
- github
- codecov

**Policies:**
- `repo-boilerplate` — readme, codeowners, gitignore, license, editorconfig, etc.
- `testing` — executed, passing, coverage
- `linter` — ran
- All 11 language policies — go (min 1.21), java (min 17), nodejs (min 18), python (min 3.9), rust (edition 2021), php (min 8.1), cpp (min std 17), dotnet (min sdk 8.0), shell (shellcheck), ruby (min 3.1), html (htmlhint, stylelint)
- `dependencies` — min-versions for common frameworks

### security

Vulnerability scanning, secret detection, supply-chain security. May optionally
use SNYK_TOKEN for enhanced SCA.

**Collectors:**
- gitleaks, trivy, syft, semgrep, codeql
- snyk (optional — needs SNYK_TOKEN)

**Policies:**
- `secrets` — no-hardcoded-secrets (block-pr), executed (score)
- `sca` — executed, max-severity (min: critical)
- `sast` — executed, max-severity (min: high)
- `container-scan` — executed, max-severity (min: critical)
- `sbom` — sbom-exists, has-licenses

### iac

Infrastructure as code, container best practices, CI/CD security.

**Collectors:**
- docker, github, github-actions
- k8s, terraform (if available)

**Policies:**
- `container` — no-latest, user, healthcheck, stable-tags
- `k8s` — k8s-specific checks
- `terraform` — terraform-specific checks
- `iac` / `iac-scan` — infrastructure scanning
- `github-actions` — no-script-injection, permissions, checkout safety
- `ci` — CI pipeline checks

### ai

AI development practices. Zero secrets required.

**Collectors:**
- ai, claude, codex, gemini, coderabbit

**Policies:**
- `ai` — instruction-file-exists, canonical-naming, instruction-file-length
- `claude` — cli-safe-flags, structured-output (claude-specific)
- `codex` — cli-safe-flags, structured-output (codex-specific)
- `gemini` — cli-safe-flags, structured-output (gemini-specific)

### soc2

SOC2 and compliance. Depends on `security` pack — inherits its scanners
rather than duplicating them. Adds compliance-specific policies on top.

**Depends on:** `security@v1` (inherits collectors: gitleaks, trivy, etc.)

**Additional collectors:**
- github (for access control and audit data)

**Policies:**
- `vcs` — branch-protection-enabled, require-pull-request, minimum-approvals, require-codeowner-review, disallow-force-push
- Additional compliance-specific policies as they're built (audit trail, access reviews, etc.)

## Overlap Map

Where packs share collectors or policies, and who should own what:

| Resource | baseline | security | iac | ai | soc2 (depends on security) |
|----------|----------|----------|-----|-----|---------------------------|
| Language collectors | ✅ owns | — | — | — | — |
| gitleaks collector | — | ✅ owns | — | — | 🔗 inherited |
| trivy/syft/semgrep | — | ✅ owns | — | — | 🔗 inherited |
| github collector | ✅ owns | — | deduped | — | deduped |
| docker collector | — | — | ✅ owns | — | — |
| github-actions collector | — | — | ✅ owns | — | — |
| ai/claude/codex/gemini | — | — | — | ✅ owns | — |
| secrets policy | — | ✅ owns | — | — | 🔗 inherited |
| sca/sast/sbom | — | ✅ owns | — | — | 🔗 inherited |
| container/container-scan | — | — | ✅ owns | — | — |
| vcs policy | — | — | — | — | ✅ owns |
| testing/linter | ✅ owns | — | — | — | — |
| repo-boilerplate | ✅ owns | — | — | — | — |
| language policies | ✅ owns | — | — | — | — |

**Key overlap points:**
- `gitleaks` collector: security owns, soc2 inherits via dependency → collector dedup (auto, safe)
- `github` collector: baseline owns, iac/soc2 also declare → collector dedup (auto, safe)
- `secrets` policy: security owns it. soc2 depends on security and inherits
  the collectors but declares its own policies — no policy duplication.

With pack dependencies, most potential overlaps are resolved structurally.
Collector dedup handles the remaining shared data sources automatically.

## Migration Path

The current copy-paste starter configs (PR #121) work today as templates.
The migration to importable packs would be:

1. **Now:** Ship copy-paste configs as-is (they work, no platform changes needed)
2. **Platform work:** Add `packs:` section support to luna-config.yml
3. **Repackage:** Convert starter configs into pack manifests (add name/version/requires metadata)
4. **Validation:** Add duplicate detection to hub-on-pull
5. **CLI:** Ship `lunar config validate` for local pre-push checking
6. **Eject (future):** `lunar config eject <pack>` expands a pack import to raw policies

The copy-paste configs in PR #121 are the content of the packs regardless of
delivery format. The curation work isn't wasted — it just gets a manifest
wrapper.

## Pros and Cons Summary

### Importable topic packs (this proposal)

**Pros:**
1. 2-3 lines for a working config — onboarding funnel conversion
2. Version bumps propagate (living recommendations, not snapshots)
3. Fleet-wide governance — audit "is every repo on security >= v2?"
4. Composable — baseline + security + ai without manual merge
5. Marketplace potential — third-party packs (HIPAA, PCI-DSS)
6. Clean topic separation minimizes conflicts
7. Include/exclude handles customization without ejecting
8. Eject available as escape hatch for power users

**Cons:**
1. Requires platform work (packs: section, validation, resolution)
2. Customization beyond exclude/with requires ejecting
3. Debugging is harder — need to resolve pack to see what's actually running
4. Specialized packs may still overlap, requiring user intervention
5. Version conflicts across packs need a resolution strategy
6. One more abstraction layer to understand

### Copy-paste configs (current PR #121)

**Pros:**
1. Ships today, no platform changes
2. Every policy visible in context — self-documenting
3. Full control from day 1
4. No abstraction to fight

**Cons:**
1. No auto-updates — manual re-copy on pack changes
2. Verbose initial setup (50-100 lines vs 2-3 lines)
3. Drift from recommended defaults over time
4. No fleet-wide governance — each repo has its own version
5. Combining packs requires manual merge

## Open Questions

1. **Pack versioning:** Do packs version independently, or follow the lunar-lib
   release? Independent versioning is more flexible but adds complexity.

2. **Collector inclusion:** Should packs include the language collectors they
   need, or should there be an implicit "all language collectors are always
   available"? Current approach includes them explicitly.

3. **Required vs. optional secrets:** How does a pack declare "SNYK_TOKEN makes
   SCA better but isn't required"? The `requires.secrets` block needs
   required vs. optional distinction.

4. **Pack discovery:** Where do users browse available packs? A hub page?
   `lunar packs list`?

5. **Org-private packs:** Can a company publish internal packs? What's the
   distribution mechanism?

6. **Validation UX:** Should `lunar config validate` produce a diff of what
   the resolved config looks like? That would help users understand what
   their pack imports actually expand to.
