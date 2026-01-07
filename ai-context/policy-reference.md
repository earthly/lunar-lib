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

## The lunar_policy SDK

Install the SDK:

```bash
pip install lunar-policy
```

**requirements.txt:**
```
lunar-policy==0.1.6
```

### Core Classes

| Class | Purpose |
|-------|---------|
| `Check` | Main class for making assertions |
| `Node` | Navigate and explore JSON data |
| `CheckStatus` | Enum of check outcomes (PASS, FAIL, PENDING, ERROR) |
| `NoDataError` | Exception for missing data |
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

with Check("k8s-valid", "All K8s manifests should be valid") as c:
    manifests = c.get_node(".k8s.manifests")
    if not manifests.exists():
        return
    
    for manifest in manifests:
        path = manifest.get_value_or_default(".path", "<unknown>")
        valid = manifest.get_value_or_default(".valid", False)
        error = manifest.get_value_or_default(".error", "Unknown error")
        
        c.assert_true(valid, f"{path}: {error}")
```

### Pattern 3: Multiple Checks in One Policy

```python
from lunar_policy import Check

def check_readme():
    with Check("readme-exists", "README should exist") as c:
        c.assert_true(c.get_value(".repo.readme_exists"), "README.md not found")

def check_readme_length():
    with Check("readme-length", "README should be substantial") as c:
        if not c.exists(".repo.readme_num_lines"):
            return
        lines = c.get_value(".repo.readme_num_lines")
        c.assert_greater_or_equal(lines, 50, f"README has only {lines} lines, need at least 50")

def main():
    check_readme()
    check_readme_length()

if __name__ == "__main__":
    main()
```

### Pattern 4: Configurable Thresholds

```python
from lunar_policy import Check, variable_or_default

def check_replicas():
    with Check("k8s-min-replicas", "HPAs should have minimum replicas") as c:
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
    with Check("k8s-pdb-coverage", "Deployments should have PDBs") as c:
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

```
my-policy/
├── lunar-policy.yml       # Required: Plugin configuration
├── main.py                # Main policy script
├── checks/                # Optional: Organize checks in subdirectory
├── helpers.py             # Optional: Helper modules
├── requirements.txt       # Must include lunar-policy
├── Dockerfile             # For policies with additional dependencies
└── test_main.py           # Optional: Unit tests
```

### requirements.txt

```
lunar-policy==0.2.2
# Add other dependencies as needed
```

### lunar-policy.yml Reference

```yaml
version: 0

name: my-policy                       # Required
description: What this policy checks  # Should always specfiy
author: team@example.com              # Required

default_image: earthly/lunar-scripts:v1.0  # Should always specify: base image or custom image

policies:
  - mainPython: main.py               # Or: runPython: "inline code"

inputs:                               # Optional
  threshold:
    description: Minimum threshold
    default: "80"
```

## Container Images

Policies must always specify a `default_image`. Use the base `earthly/lunar-scripts:v1.0` image (which includes `lunar-policy`) unless you need additional dependencies.

### Creating a Custom Image

Create a `Dockerfile` that inherits from the official base image and installs your dependencies:

```dockerfile
FROM earthly/lunar-scripts:v1.0

# Copy and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
```

### Wiring Images to the Earthfile

Add a build target in `Earthfile` to build and publish your image:

```earthfile
my-policy-image:
    FROM DOCKERFILE ./policies/my-policy
    ARG VERSION=latest
    SAVE IMAGE --push earthly/lunar-lib-my-policy:$VERSION
```

Then reference this image in your `lunar-policy.yml`:

```yaml
default_image: earthly/lunar-lib-my-policy:latest
```

If you don't need additional dependencies, use the base image:

```yaml
default_image: earthly/lunar-scripts:v1.0
```

**Important:** Always bake dependencies into the image rather than relying on runtime installation. This provides faster startup, reproducible builds, and eliminates network dependencies at runtime.

## Best Practices

### 1. Write Descriptive Check Names and Messages

```python
# Good
with Check("k8s-deployment-replicas", "Deployments should have at least 3 replicas") as c:
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

### 5. One Concern Per Check

```python
# Good - separate checks for separate concerns
def check_dockerfile_exists():
    with Check("dockerfile-exists") as c:
        c.assert_exists(".dockerfile", "No Dockerfile found")

def check_dockerfile_no_latest():
    with Check("dockerfile-no-latest") as c:
        # Check for :latest tag usage
```

### 6. Make Policies Configurable

Use inputs for thresholds and settings:

```python
min_coverage = int(variable_or_default("minCoverage", "80"))
```
