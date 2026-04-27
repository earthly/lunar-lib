# endoflife.date Collector

Detect runtime/SDK versions used by a component and check them against the [endoflife.date](https://endoflife.date) API for end-of-life and active-support status.

## Overview

This collector inspects standard pinning files in the cloned repo (`.go-version`, `go.mod`, `.nvmrc`, `package.json`, `.python-version`, `pyproject.toml`, `.ruby-version`, `Gemfile`, `.java-version`, `pom.xml`, `build.gradle`, `global.json`, `*.csproj`, `composer.json`) to figure out which runtime and version a service runs on. It then queries https://endoflife.date for the matching product cycle (e.g. Go `1.21.5` → cycle `1.21`) and writes normalized lifecycle data to `.lang.<language>.eol`. Catches "neglected legacy service" smell — components pinned to runtimes past EOL or out of active support.

The endoflife.date API is public, so no secrets or accounts are required. Network access to `https://endoflife.date` is the only runtime requirement.

## Collected Data

This collector writes to the following Component JSON paths, where `<language>` is one of `go`, `nodejs`, `python`, `ruby`, `java`, `dotnet`, `php`:

| Path | Type | Description |
|------|------|-------------|
| `.lang.<language>.eol.source` | object | Tool/integration metadata (`tool: "endoflife.date"`, `integration: "api"`, `collected_at`) |
| `.lang.<language>.eol.product` | string | endoflife.date product slug (e.g. `go`, `nodejs`, `eclipse-temurin`) |
| `.lang.<language>.eol.cycle` | string | Matched release cycle (e.g. `"1.21"` for Go, `"20"` for Node.js) |
| `.lang.<language>.eol.detected_version` | string | The full version pinned in the repo (e.g. `"1.21.5"`, `"20.11.1"`) |
| `.lang.<language>.eol.is_eol` | boolean | `true` if `eol_date` is set and is on or before today |
| `.lang.<language>.eol.is_supported` | boolean | `true` if the runtime is still in **active** support — see [Support semantics](#support-semantics) |
| `.lang.<language>.eol.eol_date` | string \| null | ISO date when the cycle reaches end-of-life; `null` if endoflife.date does not declare one |
| `.lang.<language>.eol.support_until` | string \| null | ISO date when active support ends (security-only afterward); `null` for products that don't distinguish support from EOL |
| `.lang.<language>.eol.lts` | boolean | Whether this cycle is an LTS release (also `true` if endoflife.date returns an LTS-start date) |
| `.lang.<language>.eol.latest_in_cycle` | string | Latest patch in the cycle (e.g. `"1.21.13"`) |
| `.lang.<language>.native.endoflife.product` | string | Same as `.lang.<language>.eol.product`, kept for native-data parity |
| `.lang.<language>.native.endoflife.cycle` | object | Raw cycle object as returned by `https://endoflife.date/api/<product>.json` |

If a runtime cannot be resolved for a given language (no pin file present, or the pinned version doesn't map to any endoflife.date cycle), nothing is written for that language. Absence of a `.lang.<language>.eol` key means "we couldn't determine an EOL status" — not "the runtime is supported".

## Collectors

| Collector | Description |
|-----------|-------------|
| `runtime` | Detects pinned runtime versions across Node.js, Python, Ruby, Go, Java, .NET, and PHP, then queries endoflife.date and writes EOL/support data per language. Code hook. |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/endoflife@v1.0.0
    on: ["domain:your-domain"]
    with:
      # Override only if you mirror the API internally
      # endoflife_base_url: "https://endoflife.date/api"
      # JDK distribution — see "Java distribution" section below
      # java_product: "eclipse-temurin"
      # Use "dotnet" for modern .NET, "dotnetfx" for legacy Framework
      # dotnet_product: "dotnet"
```

Pair it with the `endoflife` policy to enforce EOL and support guardrails:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/endoflife@v1.0.0
    enforcement: report-pr
```

No secrets are required.

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `endoflife_base_url` | `https://endoflife.date/api` | API base URL. Override only if you proxy/mirror the API. |
| `java_product` | `eclipse-temurin` | endoflife.date product slug used for Java. |
| `dotnet_product` | `dotnet` | endoflife.date product slug used for .NET (`dotnet` for modern, `dotnetfx` for .NET Framework). |

## Version detection

The collector attempts to detect a runtime version per language using the following pin files, in priority order. The first source that yields a parseable version wins.

| Language | Sources (in order) |
|----------|-------------------|
| Go | `.go-version`, `go.mod` (`go 1.21` or `toolchain go1.21.5`) |
| Node.js | `.nvmrc`, `.node-version`, `package.json` (`engines.node`) |
| Python | `.python-version`, `runtime.txt`, `pyproject.toml` (`requires-python`) |
| Ruby | `.ruby-version`, `Gemfile` (`ruby '3.2.0'`) |
| Java | `.java-version`, `pom.xml` (`<java.version>`, `<maven.compiler.release>`), `build.gradle` (`sourceCompatibility`, `targetCompatibility`) |
| .NET | `global.json` (`sdk.version`), first `*.csproj`/`*.fsproj`/`*.vbproj` (`<TargetFramework>net8.0</TargetFramework>`) |
| PHP | `composer.json` (`require.php` / `config.platform.php`) |

If a file declares a range or constraint (e.g. `>=3.10`, `^20.0.0`), the collector picks the lowest concrete version that satisfies the constraint, since that's the worst-case the runtime can drop to. If no concrete version can be resolved, the language is skipped.

## Cycle matching

Each detected version is matched to the most specific endoflife.date cycle. Examples:

- Go `1.21.5` → cycle `1.21`
- Node.js `20.11.1` → cycle `20`
- Python `3.11.7` → cycle `3.11`
- Ruby `3.2.0` → cycle `3.2`
- Java `17.0.9` → cycle `17`
- .NET `8.0.100` → cycle `8`
- PHP `8.2.10` → cycle `8.2`

If no matching cycle is found (for example a beta/preview version not yet listed), the collector writes nothing for that language and logs a stderr message.

## Support semantics

endoflife.date distinguishes two phases for products that have them:

- **Active support** — the runtime is receiving normal updates, including non-security fixes
- **Security/maintenance** — only critical security fixes are backported; the runtime is otherwise frozen

The collector exposes both as separate booleans so policies can pick the strictness they want:

- `is_eol = true` — past `eol_date` (no support of any kind, including security)
- `is_supported = true` — still receiving active (non-security-only) updates

For products where endoflife.date doesn't expose a separate `support` field (e.g. Go), `support_until` is `null` and `is_supported` falls back to "not EOL" (i.e. equivalent to `not is_eol`).

## Java distribution

There is no generic `java` product on endoflife.date. The default is `eclipse-temurin` (the Adoptium successor to AdoptOpenJDK), which is the most common OpenJDK distribution. If your service ships on a different distribution, set the `java_product` input to one of:

- `amazon-corretto`
- `azul-zulu`
- `bellsoft-liberica`
- `eclipse-temurin` *(default)*
- `ibm-semeru-runtime`
- `microsoft-build-of-openjdk`
- `oracle-jdk`
- `redhat-build-of-openjdk`
- `sapmachine`

These mostly track the same upstream OpenJDK release schedule but each has its own EOL/support dates, so picking the right one matters when EOL is days or weeks away.

## .NET vs .NET Framework

`dotnet_product` defaults to `dotnet`, which covers .NET 5 / 6 / 7 / 8 / 9+ (the cross-platform line). If your component is on legacy .NET Framework 4.x, set `dotnet_product: "dotnetfx"`.

## Limitations

- **Runtime pin only** — this collector reads pinned runtime versions, not the actual installed version on a deployment target. A `go.mod` that says `go 1.21` doesn't guarantee production runs Go 1.21 — that's a deployment-config concern. For runtime-detection from running services, integrate with your service-catalog tool.
- **Frameworks not covered** — endoflife.date covers many frameworks (Spring Boot, Django, Rails, etc.), but this v1 ships runtime-only checks. Framework EOL is on the roadmap but is opt-in given the false-positive risk on transitive dependencies.
- **No vendor-specific overrides** — Java's distribution choice is a single input applied across all components. Components on different JDKs in the same domain need separate `endoflife` collector instances.

## Notes on behavior

- The collector runs on the `code` hook, so it fires on each push rather than a schedule. The endoflife.date API is small and fast (sub-second responses, simple JSON), so per-push lookups are cheap.
- Network errors against endoflife.date are non-fatal: the collector logs to stderr and exits 0 without writing partial data. Policies that depend on this collector will skip when no `.lang.<language>.eol` data is present.
- Example Component JSON is defined in `lunar-collector.yml` under `example_component_json`.
