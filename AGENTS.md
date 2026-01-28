# AI Context about Lunar collectors and policies (guardrails)

This directory contains reference documentation for AI agents working with the Lunar platform.

## Reference Documentation

* [about-lunar.md](ai-context/about-lunar.md): **Start here.** High-level overview of the Lunar platform, the problem it solves, and key concepts from a user perspective.
* [core-concepts.md](ai-context/core-concepts.md): **Then read this.** Comprehensive explanation of Lunar's architecture, key entities, execution flow, and how collectors/policies interact via the Component JSON.
* [collector-reference.md](ai-context/collector-reference.md): Complete guide to writing collectors—hooks, environment variables, the `lunar collect` command, patterns, and best practices.
* [cataloger-reference.md](ai-context/cataloger-reference.md): Complete guide to writing catalogers—syncing catalog data from external systems, the `lunar catalog` command, patterns, and best practices.
* [policy-reference.md](ai-context/policy-reference.md): Complete guide to writing policies—the Check class, assertions, handling missing data, patterns, and testing.

## Component JSON Schema

The Component JSON schema documentation lives in [component-json/](ai-context/component-json/):

* [conventions.md](ai-context/component-json/conventions.md): **The schema contract.** Design principles, source metadata patterns, presence detection, PR-specific data, native data, and language-specific patterns.
* [structure.md](ai-context/component-json/structure.md): **The category reference.** Quick reference table of all paths, links to individual category docs (`.repo`, `.sca`, `.k8s`, etc.), naming conventions, and schema extension guidelines.

The `structure.md` file links to individual category files (`cat-repo.md`, `cat-sca.md`, etc.) for detailed examples and key policy paths.

## Plugin Templates

* [collector-README-template.md](ai-context/collector-README-template.md): Standard README.md template for collector plugins.
* [cataloger-README-template.md](ai-context/cataloger-README-template.md): Standard README.md template for cataloger plugins.
* [policy-README-template.md](ai-context/policy-README-template.md): Standard README.md template for policy plugins.

## Implementation Guides

* [guardrail-specs](ai-context/guardrail-specs): Guardrail specifications for the AI to implement. This contains the specifications for each guardrail, together with suggested approach to implement it.
* [strategies.md](ai-context/strategies.md): Common strategies to be used for implementing the guardrails (policy and collector plugins).

## Testing Policies and Collectors

To test policies during development, use the `lunar policy dev` command from the `pantalasa/lunar` directory (located at `/home/brandon/code/earthly/pantalasa/lunar`).

### Setup

1. **Copy your policy files** to the pantalasa/lunar policies directory:
   ```bash
   cp /home/brandon/code/earthly/lunar-lib-wt-dep-versions/policies/<policy-name>/* \
      /home/brandon/code/earthly/pantalasa/lunar/policies/<policy-name>/
   ```

2. **Run from the pantalasa/lunar directory** with the hub token:
   ```bash
   cd /home/brandon/code/earthly/pantalasa/lunar
   LUNAR_HUB_TOKEN=df11a0951b7c2c6b9e2696c048576643 lunar policy dev ...
   ```

### Running Policy Tests

Use `--script` to run a policy script directly against a component:

```bash
LUNAR_HUB_TOKEN=df11a0951b7c2c6b9e2696c048576643 lunar policy dev \
  --script ./policies/<policy-name>/<script>.py \
  --component github.com/pantalasa/backend
```

### Passing Arguments with `--with`

The `--with` flag accepts key=value pairs. **Important:** The separator between multiple arguments is the literal string `;,&` (not just a comma or semicolon).

```bash
# Single argument
--with 'language=go'

# Multiple arguments (note the ;,& separator)
--with 'language=go;,&min_versions={"github.com/sirupsen/logrus":"1.9.0"}'
```

**Limitation:** The `--with` parser only splits into 2 parts maximum, so you can only pass 2 arguments at a time via `--with`.

### Example: Testing a Policy

```bash
cd /home/brandon/code/earthly/pantalasa/lunar

# Test that policy passes with valid versions
LUNAR_HUB_TOKEN=df11a0951b7c2c6b9e2696c048576643 lunar policy dev \
  --script ./policies/dependency-versions-2/dependency-versions.py \
  --component github.com/pantalasa/backend \
  --with 'language=go;,&min_versions={"github.com/sirupsen/logrus":"1.9.0"}'

# Test that policy fails with impossible minimum version
LUNAR_HUB_TOKEN=df11a0951b7c2c6b9e2696c048576643 lunar policy dev \
  --script ./policies/dependency-versions-2/dependency-versions.py \
  --component github.com/pantalasa/backend \
  --with 'language=go;,&min_versions={"github.com/sirupsen/logrus":"99.0.0"}'
```

### Viewing Component JSON

To inspect what data is available in the component JSON:

```bash
cd /home/brandon/code/earthly/pantalasa/lunar

LUNAR_HUB_TOKEN=df11a0951b7c2c6b9e2696c048576643 lunar component get-json \
  github.com/pantalasa/backend | python3 -c "
import sys, json
d = json.load(sys.stdin)
# Example: view Go direct dependencies
deps = d.get('lang',{}).get('go',{}).get('dependencies',{}).get('direct',[])
print(json.dumps(deps[:5], indent=2))
"
```

### Available Test Components

The following components are configured in pantalasa/lunar for testing:

| Component | Tags | Language |
|-----------|------|----------|
| `github.com/pantalasa/backend` | backend, go, SOC2 | Go |
| `github.com/pantalasa/frontend` | frontend, nodejs | Node.js |
| `github.com/pantalasa/auth` | backend, python, SOC2 | Python |
| `github.com/pantalasa/spring-petclinic` | backend, java, SOC2 | Java |
| `github.com/pantalasa/inventory` | backend, java, SOC2 | Java |
