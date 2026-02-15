# Policy Reference

This document provides comprehensive documentation for writing Lunar policies—Python scripts that evaluate the Component JSON and produce pass/fail checks.

## What is a Policy?

A **policy** is a Python script that:
1. Reads data from the Component JSON (collected by collectors)
2. Makes assertions about that data
3. Produces **checks** with pass/fail/pending/error outcomes

Policies are the enforcement mechanism for your engineering standards.

## Policy Definition

Policies are defined in `lunar-config.yml` or as plugins in `lunar-policy.yml`.

### Inline Policy (in lunar-config.yml)

```yaml
policies:
  # Run form - inline script
  - name: readme-exists
    description: Repository should have a README.md file
    runPython: |
      from lunar_policy import Check
      with Check("readme-exists", "README.md should exist") as c:
          c.assert_true(c.get_value(".repo.readme_exists"), "README.md not found")
    on: ["domain:payments"]
    enforcement: block-pr

  # Main form - reference a script file
  - name: k8s-policies
    mainPython: ./policies/k8s/main.py
    on: [kubernetes]
    enforcement: report-pr
```

### Plugin Policy (in lunar-policy.yml)

```yaml
version: 0

name: my-policy
description: Validates XYZ requirements
author: team@example.com

policies:
  - mainPython: main.py

inputs:
  min_coverage:
    description: Minimum required code coverage percentage
    default: "80"
```

**Usage in lunar-config.yml:**

```yaml
policies:
  - uses: ./policies/my-policy
    on: ["domain:payments"]
    enforcement: block-pr
    with:
      min_coverage: "90"
```

## Enforcement Levels

The `enforcement` field controls how policy failures affect the development workflow:

| Level | PR Comments | Blocks PR | Blocks Release | Use Case |
|-------|-------------|-----------|----------------|----------|
| `draft` | No | No | No | Testing new policies |
| `score` | No | No | No | Tracking/dashboards only |
| `report-pr` | Yes | No | No | Awareness without blocking |
| `block-pr` | Yes | Yes | No | Must fix before merge |
| `block-release` | No | No | Yes | Critical for production |
| `block-pr-and-release` | Yes | Yes | Yes | Maximum enforcement |

**Recommended rollout:** `draft` → `score` → `report-pr` → `block-pr`

### Additional Policy Configuration

#### `runs_on`

Controls when the policy runs:

```yaml
policies:
  - uses: ./policies/coverage
    on: [backend]
    runs_on: [prs, default-branch]  # Default: runs on both
    enforcement: block-pr
```

| Value | Meaning |
|-------|---------|
| `prs` | Run on pull requests |
| `default-branch` | Run on the default branch (main/master) |

Default is `[prs, default-branch]`. Use `runs_on: [prs]` to run only on PRs, or `runs_on: [default-branch]` to run only on the main branch.

#### `initiative`

Groups related policies for management and reporting:

```yaml
policies:
  - uses: ./policies/security-scan
    on: [backend]
    initiative: security-q1  # Groups this policy under "security-q1"
    enforcement: block-pr
```

If not specified, policies are associated with the built-in "default" initiative.

#### `include` and `exclude`

When importing a policy plugin that defines multiple sub-policies, selectively enable or disable specific checks:

```yaml
policies:
  # Include only specific checks
  - uses: ./policies/container
    on: [docker]
    include: [no-latest, healthcheck]  # Only run these two checks

  # Exclude specific checks
  - uses: ./policies/container
    on: [docker]
    exclude: [user]  # Run all checks except "user"
```

If neither `include` nor `exclude` is specified, all sub-policies are included by default.

## The lunar_policy SDK

Install the SDK:

```bash
pip install lunar-policy
```

**requirements.txt:**
```
lunar-policy==0.2.2
```

### Core Classes

| Class | Purpose |
|-------|---------|
| `Check` | Main class for making assertions |
| `Node` | Navigate and explore JSON data |
| `CheckStatus` | Enum of check outcomes (PASS, FAIL, PENDING, ERROR, SKIPPED) |
| `NoDataError` | Exception for missing data |
| `SkippedError` | Exception to skip inapplicable checks |
| `variable_or_default` | Access policy inputs |

## The Check Class

The `Check` class is the primary interface for writing policies.

### Basic Usage

```python
from lunar_policy import Check

with Check("check-name", "Human-readable description") as c:
    # Make assertions
    c.assert_true(c.get_value(".some.path"), "Failure message")
```

### Constructor

```python
Check(name, description=None, node=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Unique identifier for this check |
| `description` | str | Human-readable description (shown in UI) |
| `node` | Node | Optional: custom data source (for testing) |

### Data Access Methods

#### get_value(path)

Retrieves data from the Component JSON.

```python
# Get a value at a path
readme_exists = c.get_value(".repo.readme_exists")
coverage = c.get_value(".coverage.percentage")

# Get nested data
first_image = c.get_value(".dockerfile.images[0]")

# Get root data
all_data = c.get_value()  # or c.get_value(".")
```

**Missing data behavior:**
- Before collectors finish → raises `NoDataError` → check becomes `pending`
- After collectors finish → raises `ValueError` → check becomes `error`

#### get_value_or_default(path, default)

Returns a default value if path doesn't exist.

```python
# Returns 0 if .coverage.percentage doesn't exist
coverage = c.get_value_or_default(".coverage.percentage", 0)

# Returns empty list if .tags doesn't exist
tags = c.get_value_or_default(".tags", [])
```

**Use this when missing data is acceptable, not a pending state.**

#### get_node(path)

Gets a `Node` object for navigation and exploration.

```python
k8s = c.get_node(".k8s")
if k8s.exists():
    for descriptor in k8s.get_node(".descriptors"):
        valid = descriptor.get_value(".valid")
```

#### exists(path)

Checks if a path exists.

```python
if c.exists(".coverage"):
    # Coverage data is available
    coverage = c.get_value(".coverage.percentage")
```

**Missing data behavior:**
- Before collectors finish → raises `NoDataError` → check becomes `pending`
- After collectors finish → returns `False`

#### get_all_values(path)

Gets all values at a path across all collected deltas (for paths collected multiple times).

```python
# If multiple CI jobs collected to .builds[]
all_builds = c.get_all_values(".builds")
```

### Assertion Methods

All assertions record their result and continue execution (they don't raise exceptions on failure).

#### assert_true(value, failure_message)

```python
c.assert_true(c.get_value(".repo.readme_exists"), "README.md not found")
c.assert_true(coverage >= 80, f"Coverage {coverage}% is below 80%")
```

#### assert_false(value, failure_message)

```python
c.assert_false(c.get_value(".has_vulnerabilities"), "Security vulnerabilities found")
```

#### assert_equals(value, expected, failure_message)

```python
c.assert_equals(c.get_value(".config.version"), "2.0", "Config version must be 2.0")
```

#### assert_exists(path, failure_message)

Asserts that a path exists in the Component JSON.

```python
c.assert_exists(".coverage", "Coverage data not found")
```

**Behavior:**
- Before collectors finish → `pending`
- After collectors finish, path missing → `fail`
- Path exists → continues

#### assert_contains(value, expected, failure_message)

```python
# For strings
c.assert_contains(c.get_value(".readme.content"), "## Installation", "README missing Installation section")

# For lists
c.assert_contains(c.get_value(".tags"), "production", "Missing 'production' tag")
```

#### assert_greater(value, threshold, failure_message)

```python
c.assert_greater(c.get_value(".coverage.percentage"), 80, "Coverage must be greater than 80%")
```

#### assert_greater_or_equal(value, threshold, failure_message)

```python
c.assert_greater_or_equal(c.get_value(".replicas"), 3, "Need at least 3 replicas")
```

#### assert_less(value, threshold, failure_message)

```python
c.assert_less(c.get_value(".complexity"), 15, "Cyclomatic complexity too high")
```

#### assert_less_or_equal(value, threshold, failure_message)

```python
c.assert_less_or_equal(c.get_value(".build.duration_minutes"), 10, "Build too slow")
```

#### assert_match(value, pattern, failure_message)

```python
c.assert_match(c.get_value(".version"), r"^\d+\.\d+\.\d+$", "Version must be semver")
```

#### fail(message)

Unconditionally fails the check.

```python
if some_complex_condition:
    c.fail("Custom failure reason")
```

#### skip(reason)

Unconditionally skips the check. Use this **only** for applicability filtering—when the check doesn't apply to the current component type.

```python
# CORRECT: Skip when check doesn't apply to this component type
if not c.exists(".lang.go"):
    c.skip("This check only applies to Go projects")

# CORRECT: Skip when relevant files don't exist
if not c.exists(".k8s"):
    c.skip("No Kubernetes manifests in this repository")
```

**When to use `skip()`:**
- The check is language-specific and the component uses a different language
- The check requires specific files/config that don't exist (e.g., K8s checks on a repo without manifests)
- The check is for a specific component type that doesn't match

**When NOT to use `skip()`:**
- **Policy misconfiguration**: If required inputs are missing or invalid, raise an error instead. Users should know immediately that their policy isn't working.
- **Missing component data**: Use `assert_exists()` or `get_value()` instead—these handle pending vs permanently missing data correctly (see [Handling Missing Data](#handling-missing-data)).

```python
# BAD: Don't skip for misconfiguration - error instead
allowed = variable_or_default("allowed_registries", "")
if not allowed:
    c.skip("No registries configured")  # ❌ Wrong - user won't know policy is broken

# GOOD: Raise an error for misconfiguration
if not allowed:
    raise ValueError("Policy misconfiguration: 'allowed_registries' must be configured")

# BAD: Don't skip for missing data - use assert_exists
if not c.exists(".coverage"):
    c.skip("No coverage data")  # ❌ Wrong - masks pending/missing data

# GOOD: Use assert_exists for required data
c.assert_exists(".coverage", "Coverage data not found")
```

### Iteration Methods

```python
# Iterate over array elements
for item in c.get_node(".items"):
    name = item.get_value(".name")

# Iterate over object keys
for key in c:
    print(f"Top-level key: {key}")

# Get key-value pairs
for key, value_node in c.items():
    print(f"{key}: {value_node.get_value()}")
```

## The Node Class

`Node` provides navigation within JSON data.

### Creating Nodes

```python
from lunar_policy import Node

# From a Check
node = c.get_node(".k8s.descriptors")

# For testing - from raw data
test_data = {"foo": {"bar": 123}}
node = Node.from_component_json(test_data)
```

### Node Methods

```python
# Get value at this node or relative path
value = node.get_value()
nested = node.get_value(".nested.path")

# Get with default
value = node.get_value_or_default(".missing", "default")

# Check existence
if node.exists():
    # ...

# Get child node
child = node.get_node(".child")

# Iterate
for item in node:
    # For arrays: item is a Node
    # For objects: item is a key string
```

## Check Outcomes

| Status | Meaning | Cause |
|--------|---------|-------|
| `PASS` | Check passed | All assertions satisfied |
| `FAIL` | Check failed | One or more assertions failed |
| `PENDING` | Awaiting data | `NoDataError` raised, collectors still running |
| `ERROR` | Execution error | Exception in policy code, or missing data after collectors finished |
| `SKIPPED` | Not applicable | `SkippedError` raised (check doesn't apply to this component) |

## Handling Missing Data

Lunar policies must handle **partial data** gracefully because collectors run asynchronously.

### The NoDataError Flow

```python
with Check("coverage-check") as c:
    # If .coverage doesn't exist yet:
    # - Before collectors finish → NoDataError → status becomes PENDING
    # - After collectors finish → ValueError → status becomes ERROR
    coverage = c.get_value(".coverage.percentage")
    c.assert_greater_or_equal(coverage, 80, "Coverage too low")
```

### Pattern: Conditional Checks with exists()

```python
with Check("optional-coverage") as c:
    if c.exists(".coverage"):
        # Only check if coverage data is available
        coverage = c.get_value(".coverage.percentage")
        c.assert_greater_or_equal(coverage, 80, "Coverage too low")
    # If .coverage doesn't exist: check passes (no assertions made)
```

### Pattern: Required Data with assert_exists()

```python
with Check("required-coverage") as c:
    # Explicitly require the data to exist
    c.assert_exists(".coverage", "Coverage data not found - ensure coverage collector is configured")
    coverage = c.get_value(".coverage.percentage")
    c.assert_greater_or_equal(coverage, 80, "Coverage too low")
```

### Pattern: Safe Defaults

```python
with Check("lenient-check") as c:
    # Use default if data missing (won't go pending)
    replicas = c.get_value_or_default(".k8s.replicas", 1)
    c.assert_greater_or_equal(replicas, 3, f"Need 3 replicas, found {replicas}")
```

## Environment Variables

Policies have access to these environment variables:

| Variable | Description |
|----------|-------------|
| `LUNAR_COMPONENT_ID` | Component identifier (e.g., `github.com/acme/api`) |
| `LUNAR_COMPONENT_DOMAIN` | Component's domain |
| `LUNAR_COMPONENT_OWNER` | Component owner email |
| `LUNAR_COMPONENT_PR` | PR number (if applicable) |
| `LUNAR_COMPONENT_GIT_SHA` | Git SHA being evaluated |
| `LUNAR_COMPONENT_TAGS` | Component tags (JSON array) |
| `LUNAR_COMPONENT_META` | Component metadata (JSON) |
| `LUNAR_POLICY_NAME` | Name of the current policy |
| `LUNAR_INITIATIVE_NAME` | Initiative the policy belongs to |
| `LUNAR_SECRET_<NAME>` | Secrets (avoid using in policies—prefer collectors) |

## Policy Inputs

Use `variable_or_default` to access configurable inputs:

```python
from lunar_policy import Check, variable_or_default

with Check("coverage-check") as c:
    # Get input with default
    min_coverage = int(variable_or_default("minCoverage", "80"))
    
    coverage = c.get_value(".coverage.percentage")
    c.assert_greater_or_equal(coverage, min_coverage, 
        f"Coverage {coverage}% is below required {min_coverage}%")
```

**lunar-policy.yml:**
```yaml
inputs:
  minCoverage:
    description: Minimum required coverage percentage
    default: "80"
```

**lunar-config.yml:**
```yaml
policies:
  - uses: ./policies/coverage
    on: [backend]
    with:
      minCoverage: "90"  # Override default
```

### Input Configuration Patterns

Policy configuration should generally have reasonable defaults, but the right approach depends on the type of setting.

#### Pattern: Sensible Universal Defaults

For settings with a universally sensible default (e.g., thresholds, counts), use `variable_or_default` with a reasonable value:

```python
min_coverage = int(variable_or_default("minCoverage", "80"))  # 80% is sensible
max_complexity = int(variable_or_default("maxComplexity", "15"))  # widely accepted
```

#### Pattern: No Default for User-Dependent Settings

When the correct value depends on internal infrastructure or conventions (e.g., internal registry URLs, team-specific values), **do not provide a default**. The policy should raise an error when not configured.

**Why raise an error?** A misconfigured policy that silently passes is dangerous—it gives false confidence that checks are running when they're not. By raising an error, the misconfiguration surfaces immediately as an `error` status in the Lunar UI, alerting the platform team to fix it. This is far better than a silent pass that masks the problem:

```python
from lunar_policy import variable_or_default

# No sensible default - depends on organization's infrastructure
registry_url = variable_or_default("internal_registry", "")
if not registry_url:
    raise ValueError(
        "Policy misconfiguration: 'internal_registry' must be configured. "
        "Set this to your organization's container registry URL."
    )
```

#### Pattern: Allow-Lists vs Block-Lists

The behavior for empty lists depends on the semantic type:

**Allow-list (empty = error):** An allow-list defines what IS permitted. An empty allow-list means "nothing is allowed", which is almost always a misconfiguration—not a valid policy state.

```python
# ALLOW-LIST: error if empty
allowed_str = variable_or_default("allowed_registries", "docker.io")
allowed = [r.strip() for r in allowed_str.split(",") if r.strip()]

if not allowed:
    raise ValueError(
        "Policy misconfiguration: 'allowed_registries' is empty. "
        "An allow-list must contain at least one entry. "
        "Configure allowed registries or exclude this check."
    )

# Now check against the allow-list
if registry not in allowed:
    c.fail(f"Registry '{registry}' not in allowed list")
```

**Block-list (empty = pass early):** A block-list defines what is NOT permitted. An empty block-list means "nothing is blocked", which is a valid (lenient) configuration.

```python
# BLOCK-LIST: pass early if empty
blocked_str = variable_or_default("blocked_licenses", "")
blocked = [l.strip() for l in blocked_str.split(",") if l.strip()]

if not blocked:
    return  # No licenses blocked - policy passes

# Now check against the block-list
if license in blocked:
    c.fail(f"License '{license}' is blocked")
```

**Requirement-list (empty = pass early):** Similar to block-lists, a requirement-list that's empty means "no additional requirements", which is valid:

```python
# REQUIREMENT-LIST: pass early if empty
required_str = variable_or_default("required_labels", "")
required = [l.strip() for l in required_str.split(",") if l.strip()]

if not required:
    return  # No labels required - policy passes

# Now check for required items
for label in required:
    if label not in labels:
        c.fail(f"Missing required label: {label}")
```

**Key distinction:**
- **Allow-list empty → ERROR** (misconfiguration: nothing would be allowed)
- **Block-list empty → PASS** (valid: nothing is blocked)
- **Requirement-list empty → PASS** (valid: no extra requirements)

## Common Patterns

### Pattern 1: Boolean Value vs Data Existence

**Important distinction:** The assertion approach depends on how the collector records data.

**Case A: Collector writes explicit true/false values**

When a collector explicitly writes both success and failure cases (e.g., `lunar collect -j ".repo.readme_exists" false`), use `assert_true` on the value:

```python
from lunar_policy import Check

# Works because the readme collector writes: 
#   - true if README exists
#   - false if README is missing
with Check("readme-exists", "Repository should have a README") as c:
    c.assert_true(c.get_value(".repo.readme_exists"), "README.md not found")
```

**Case B: Collector only writes on success (absence = failure)**

When a collector only fires in certain conditions (e.g., CI hook that triggers only when a specific tool runs), the "failure" case means the data is missing entirely. Use `assert_exists`:

```python
from lunar_policy import Check

# The SCA collector only writes data when a scanner runs.
# If no scanner runs, .sca won't exist at all.
with Check("sca-scanner-ran", "SCA scanner should run in CI") as c:
    c.assert_exists(".sca", 
        "No SCA scanner detected. Configure Snyk or Semgrep in your CI pipeline.")
```

**Rule of thumb:**
- Use `assert_true(get_value(...))` when the collector writes both `true` and `false`
- Use `assert_exists(...)` when data absence indicates failure

**Avoid `get_value_or_default` for existence checks.** It's tempting to write:

```python
# BAD - masks missing data, reports false negative initially, but then later it might pass
sca_data = c.get_value_or_default(".sca", None)
c.assert_true(sca_data is not None, "SCA not run")
```

The problem: this reports FAIL while CI is still running (before SCA triggers), then flips to PASS later. The correct behavior is PENDING initially, then the real result. Use `assert_exists` instead.

**When IS `get_value_or_default` appropriate?** Use it for optional fields *within* already-collected data:

```python
# GOOD - K8s manifest was collected; namespace is optional (defaults to "default")
ns = desc.get_value_or_default(".contents.metadata.namespace", "default")

# GOOD - Container resources are optional in K8s
cpu_limit = container.get_value_or_default(".resources.limits.cpu", None)
if cpu_limit is None:
    c.fail(f"Container {name} missing CPU limit")
```

### Pattern 2: Iterating Over Collections

```python
from lunar_policy import Check

with Check("manifests-valid", "All K8s manifests should be valid") as c:
    manifests = c.get_node(".k8s.manifests")
    if not manifests.exists():
        return
    
    for manifest in manifests:
        path = manifest.get_value_or_default(".path", "<unknown>")
        valid = manifest.get_value_or_default(".valid", False)
        error = manifest.get_value_or_default(".error", "Unknown error")
        
        c.assert_true(valid, f"{path}: {error}")
```

### Pattern 3: One Check Per File (Recommended)

The recommended approach is to define each check as a separate policy entry in `lunar-policy.yml`, with each check in its own file. This allows users to selectively enable/disable checks via the `include` mechanism.

**lunar-policy.yml:**
```yaml
policies:
  - name: readme-exists
    description: README should exist
    mainPython: ./readme_exists.py

  - name: readme-length
    description: README should be substantial
    mainPython: ./readme_length.py
```

**readme_exists.py:**
```python
from lunar_policy import Check

def main(node=None):
    c = Check("readme-exists", "README should exist", node=node)
    with c:
        c.assert_true(c.get_value(".repo.readme_exists"), "README.md not found")
    return c

if __name__ == "__main__":
    main()
```

**readme_length.py:**
```python
from lunar_policy import Check

def main(node=None):
    c = Check("readme-length", "README should be substantial", node=node)
    with c:
        if not c.exists(".repo.readme_num_lines"):
            return c
        lines = c.get_value(".repo.readme_num_lines")
        c.assert_greater_or_equal(lines, 50, f"README has only {lines} lines, need at least 50")
    return c

if __name__ == "__main__":
    main()
```

Users can then selectively enable checks:
```yaml
policies:
  - uses: ./policies/readme
    include: [readme-exists]  # Only run readme-exists, skip readme-length
```

### Pattern 4: Configurable Thresholds

```python
from lunar_policy import Check, variable_or_default

def check_replicas():
    with Check("min-replicas", "HPAs should have minimum replicas") as c:
        min_required = int(variable_or_default("minReplicas", "3"))
        
        hpas = c.get_node(".k8s.hpas")
        if not hpas.exists():
            return
        
        for hpa in hpas:
            name = hpa.get_value_or_default(".name", "<unknown>")
            min_replicas = hpa.get_value_or_default(".min_replicas", 0)
            
            c.assert_greater_or_equal(min_replicas, min_required,
                f"HPA {name} has min_replicas={min_replicas}, need at least {min_required}")
```

### Pattern 5: Cross-Referencing Data

```python
from lunar_policy import Check

def check_pdb_coverage():
    """Ensure each Deployment has a PodDisruptionBudget."""
    with Check("pdb-coverage", "Deployments should have PDBs") as c:
        workloads = c.get_node(".k8s.workloads")
        pdbs = c.get_node(".k8s.pdbs")
        
        if not workloads.exists():
            return
        
        # Get list of workloads that have PDBs (by target_workload reference)
        pdb_targets = set()
        if pdbs.exists():
            for pdb in pdbs:
                target = pdb.get_value_or_default(".target_workload", "")
                if target:
                    pdb_targets.add(target)
        
        # Check each Deployment has a matching PDB
        for workload in workloads:
            kind = workload.get_value_or_default(".kind", "")
            if kind != "Deployment":
                continue
            
            name = workload.get_value_or_default(".name", "<unknown>")
            path = workload.get_value_or_default(".path", "")
            
            has_pdb = name in pdb_targets
            c.assert_true(has_pdb, f"Deployment {name} ({path}) has no matching PDB")
```

### Pattern 6: Using Component Metadata

```python
import os
import json
from lunar_policy import Check

def check_tier1_requirements():
    """Tier 1 services have stricter requirements."""
    with Check("tier1-compliance", "Tier 1 services must meet extra requirements") as c:
        tags = json.loads(os.environ.get("LUNAR_COMPONENT_TAGS", "[]"))
        
        if "tier1" not in tags:
            return  # Only applies to tier1 services
        
        # Tier 1 must have coverage > 90%
        coverage = c.get_value(".coverage.percentage")
        c.assert_greater(coverage, 90, "Tier 1 services need >90% coverage")
        
        # Tier 1 must have PagerDuty configured
        c.assert_exists(".pagerduty.policy_id", "Tier 1 services need PagerDuty")
```

## Unit Testing Policies

### Basic Test Structure

```python
import unittest
from lunar_policy import Check, Node, CheckStatus

def check_readme(node=None):
    """The policy function - accepts optional node for testing."""
    c = Check("readme-exists", node=node)
    with c:
        c.assert_true(c.get_value(".repo.readme_exists"), "README not found")
    return c

class TestReadmePolicy(unittest.TestCase):
    def test_readme_exists_passes(self):
        data = {"repo": {"readme_exists": True}}
        node = Node.from_component_json(data)
        check = check_readme(node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_readme_missing_fails(self):
        data = {"repo": {"readme_exists": False}}
        node = Node.from_component_json(data)
        check = check_readme(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("README not found", check.failure_reasons[0])

if __name__ == "__main__":
    unittest.main()
```

### Testing with node Parameter

Structure your policy functions to accept an optional `node`:

```python
def my_policy_check(node=None):
    c = Check("my-check", node=node)
    with c:
        # ... assertions ...
    return c

# Production usage (node loaded from environment)
if __name__ == "__main__":
    my_policy_check()

# Test usage (node provided explicitly)
def test_my_policy():
    node = Node.from_component_json({"test": "data"})
    check = my_policy_check(node)
    assert check.status == CheckStatus.PASS
```

## Plugin Structure

The recommended structure is **one check per policy entry**, with each check in its own file in the plugin root. This allows users to selectively enable/disable individual checks via the `include` mechanism.

```
my-policy/
├── lunar-policy.yml       # Required: Plugin configuration
├── check_one.py           # One file per check
├── check_two.py
├── check_three.py
├── helpers.py             # Optional: Shared helpers
├── requirements.txt       # Must include lunar-policy
├── Dockerfile             # For policies with additional dependencies
└── README.md              # Documentation
```

### requirements.txt

```
lunar-policy==0.2.2
# Add other dependencies as needed
```

### lunar-policy.yml Reference

Each policy in the `policies:` array should have a unique `name` and point to its own check file. Users can then select which checks to run using `include: [check-one, check-two]` in their `lunar-config.yml`.

```yaml
version: 0

name: my-policy                       # Required: Must match directory name
description: What this policy checks  # Required: Brief description
author: team@example.com              # Required

default_image: earthly/lunar-scripts:1.0.0  # Recommended: specify base or custom image

# === Landing page metadata (required for public plugins) ===
landing_page:
  display_name: "My Policies"         # Required: Max 50 chars, must end with "Policies"
  long_description: |                 # Required: Max 300 chars, used for hero tagline + meta description
    Enforce XYZ standards across your codebase. Validates ABC 
    configurations and ensures DEF compliance.
  category: "security-and-compliance" # Required: See categories below
  status: "stable"                    # Required: stable|beta|experimental|deprecated
  icon: "assets/my-icon.svg"          # Required: Path relative to plugin directory
  
  # Required collectors - policies MUST specify at least one
  requires:
    - slug: "my-collector"            # Plugin directory name
      type: "collector"               # Must be "collector"
      reason: "Provides data that this policy evaluates"  # Max 80 chars
  
  # Related plugins for cross-linking (optional)
  related:
    - slug: "other-policy"
      type: "policy"
      reason: "Also enforces related standards"

# === Policies (sub-components) ===
policies:
  - name: check-one                   # Required: Unique name for this check
    description: |                    # Required: Multi-line description
      Validates X exists and is properly configured.  # Describe WHAT is checked, not HOW.
      Checks for common misconfigurations.             # Don't mention Component JSON paths
                                                       # or implementation details.
    mainPython: check_one.py
    keywords: ["keyword1", "keyword2", "seo term"]  # Required: SEO keywords

  - name: check-two
    description: Ensures Y meets requirements
    mainPython: check_two.py
    keywords: ["keyword3", "keyword4"]

# === Inputs (optional) ===
inputs:
  threshold:
    description: Minimum threshold percentage
    default: "80"
  allowed_values:
    description: Comma-separated list of allowed values
    default: "value1,value2"
```

### Landing Page Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `landing_page.display_name` | Yes | Human-readable name, max 50 chars, must end with "Policies" |
| `landing_page.long_description` | Yes | Marketing description, max 300 chars, used for hero + meta |
| `landing_page.category` | Yes | One of the 6 valid categories (see below) |
| `landing_page.status` | Yes | `stable`, `beta`, `experimental`, or `deprecated` |
| `landing_page.icon` | Yes | Path to SVG icon relative to plugin directory (file must exist) |
| `landing_page.requires[]` | Yes | Array of required collectors (`slug`, `type: collector`, `reason` max 80 chars) |
| `landing_page.related[]` | No | Array of related plugins (`slug`, `type`, `reason` max 80 chars) |
| `policies[].keywords` | Yes | Array of SEO keywords for this sub-policy (at least 1) |
| `inputs` | No | Configuration inputs (for website display, moved from README) |

**Cross-validation:** The README title (`# ...`) must match `landing_page.display_name` exactly.

### Categories

| Slug | Display Name |
|------|--------------|
| `repository-and-ownership` | Repository & Ownership |
| `deployment-and-infrastructure` | Deployment & Infrastructure |
| `testing-and-quality` | Testing & Quality |
| `devex-build-and-ci` | DevEx, Build & CI |
| `security-and-compliance` | Security & Compliance |
| `operational-readiness` | Operational Readiness |

### Status Values

| Status | Description |
|--------|-------------|
| `stable` | Production ready, well tested |
| `beta` | Feature complete, API stable |
| `experimental` | Early development, API may change |
| `deprecated` | No longer recommended |

#### `default_image`

The Docker image to use for running the policy. This overrides the global `default_image_policies` setting from `lunar-config.yml`.

**Recommended:** Always use a container image for policies:
- `earthly/lunar-scripts:1.0.0` — Official base image with Python, Bash, `lunar` CLI, and `lunar-policy` pre-installed
- Custom image inheriting from `earthly/lunar-scripts` with additional dependencies baked in

Individual policies can override this with their own `image` field.

**Why one check per policy entry?**
- Users can selectively enable checks: `include: [check-one, check-three]`
- Each check appears as a separate item in the Lunar UI
- Follows the "one concern per check" best practice
- Easier to maintain and test individually

## Container Images

Lunar runs policies inside Docker containers, providing isolation, reproducibility, and simplified dependency management.

**Recommendation:** Always use the official `earthly/lunar-scripts:1.0.0` image (or a custom image that inherits from it) for policies. This ensures consistent execution across environments.

### Image Resolution Order

The image used to run a policy is determined in this order (first match wins):

1. **Policy-level `image`** — Set directly on the policy in `lunar-config.yml`
2. **Plugin-level `default_image`** — Set in `lunar-policy.yml`
3. **Global `default_image_policies`** — Set in `lunar-config.yml`
4. **Global `default_image`** — Set in `lunar-config.yml`
5. **Implicit default** — `native` (no container) — **not recommended for policies**

### Global Default Images

Configure default images in `lunar-config.yml`:

```yaml
version: 0

default_image: earthly/lunar-scripts:1.0.0    # Recommended: use for all scripts
default_image_policies: earthly/lunar-scripts:1.0.0  # Default for policies

# ... rest of configuration
```

### Official Image: `earthly/lunar-scripts`

Lunar provides an official Docker image that includes:

- Alpine Linux (or `-debian` variant if needed)
- Python 3 with venv
- Bash
- The `lunar-policy` Python package
- The `lunar` CLI
- Common tools: `jq`, `yq`, `curl`, `parallel`, `wget`

**For development**, the image automatically executes any `requirements.txt` and/or `install.sh` files found in the plugin directory.

**For production**, bake all dependencies directly into your image for faster startup, reproducible builds, and elimination of network dependencies.

### Creating a Custom Image

Create a `Dockerfile` that inherits from the official base image:

```dockerfile
FROM earthly/lunar-scripts:1.0.0

# Install additional system dependencies (if needed)
RUN apk add --no-cache git make

# Copy and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
```

### Building and Publishing the Image

Build and push the image to your container registry:

```bash
docker build -t your-registry/my-policy:1.0.0 ./policies/my-policy
docker push your-registry/my-policy:1.0.0
```

Then reference this image in your `lunar-policy.yml`:

```yaml
default_image: your-registry/my-policy:1.0.0
```

If you don't need additional dependencies, use the base image:

```yaml
default_image: earthly/lunar-scripts:1.0.0
```

**Important:** Always bake dependencies into the image rather than relying on runtime installation. This provides faster startup, reproducible builds, and eliminates network dependencies at runtime.

## Test Locally

Use `lunar policy dev` to test policies in development mode. Run from your config directory (where `lunar-config.yml` lives).

```bash
# Pipe collector output directly into policy
lunar collector dev <collector-name> --component-dir <path> | \
  lunar policy dev <policy-name> --component-json - --verbose

# Run against a saved JSON file
lunar policy dev <policy-name> --component-json path/to/component.json --verbose

# Run against a remote component's latest data from Hub
lunar policy dev <policy-name> --component github.com/org/repo --verbose

# Pass input overrides
lunar collector dev <collector-name> --component-dir <path> | \
  lunar policy dev <policy-name> --component-json - --verbose --with "min_lines=50,max_lines=200"
```

| Flag | Description |
|------|-------------|
| `--component-json <path-or->` | Component JSON file, or `-` for stdin |
| `--component <id>` | Remote component (fetches latest data from Hub) |
| `--verbose` | Show detailed check results |
| `--with <args>` | Override policy inputs (comma-separated key=value) |
| `--output <format>` | `list` (default, human-readable) or `json` (raw) |
| `--pr <num>` | Simulate PR context |

**Note:** The name argument uses prefix matching — `my-policy` runs all sub-policies named `my-policy.*`.

## Best Practices

### 1. Write Descriptive Check Names and Messages

```python
# Good
with Check("deployment-replicas", "Deployments should have at least 3 replicas") as c:
    c.assert_greater_or_equal(replicas, 3, 
        f"Deployment {name} has {replicas} replicas, minimum is 3")

# Bad
with Check("check1") as c:
    c.assert_true(replicas >= 3, "failed")
```

### 2. Handle Missing Data Appropriately

Choose the right approach based on whether data is required:

```python
# Data is required (should fail if missing after collectors finish)
c.assert_exists(".coverage", "Coverage data required")

# Data is optional (skip check if missing)
if c.exists(".coverage"):
    # ...

# Data has a sensible default
value = c.get_value_or_default(".optional.setting", "default")
```

### 3. Include Context in Failure Messages

```python
# Good - includes file location and specific values
c.assert_true(valid, f"{file_path}: K8s manifest invalid: {error}")

# Bad - no context
c.assert_true(valid, "Invalid manifest")
```

### 4. Keep Policies Fast

Policies are re-evaluated frequently. Avoid:
- External API calls (use collectors instead)
- Heavy computation
- File I/O

### 5. One Concern Per Check, One Check Per Policy Entry

Each check should focus on a single concern and be defined as a separate policy entry in `lunar-policy.yml`. This allows users to selectively enable/disable individual checks.

```yaml
# lunar-policy.yml - Good: separate policy entries
policies:
  - name: dockerfile-exists
    mainPython: dockerfile_exists.py

  - name: dockerfile-no-latest  
    mainPython: no_latest.py
```

See [Plugin Structure](#plugin-structure) for the recommended file organization.

### 6. Make Policies Configurable

Use inputs for thresholds and settings:

```python
min_coverage = int(variable_or_default("minCoverage", "80"))
```
