# endoflife.date Collector

Resolve detected runtime versions against the [endoflife.date](https://endoflife.date) API for end-of-life and active-support status, using version data already populated by per-language collectors.

## Overview

This collector reads `.lang.<language>.version` from the component's persisted JSON (populated by per-language collectors like `golang`, `nodejs`, `python`, etc.) and queries [endoflife.date](https://endoflife.date) to find the matching release cycle (Go `1.21.5` → cycle `1.21`, Node.js `20.11.1` → cycle `20`). It then writes normalized lifecycle data to `.lang.<language>.eol`. The endoflife.date API is public — no secrets or accounts are required, only network access. Coverage of new language plugins is data-driven via the `language_products` input — add an entry mapping the language name to its endoflife.date product slug and the collector picks it up with no code changes.

## Collected Data

This collector writes to the following Component JSON paths, where `<language>` is any key configured in the `language_products` input (defaults: `go`, `nodejs`, `python`, `ruby`, `java`, `dotnet`, `php`):

| Path | Type | Description |
|------|------|-------------|
| `.lang.<language>.eol.source` | object | Tool/integration metadata (`tool: "endoflife.date"`, `integration: "api"`, `collected_at`) |
| `.lang.<language>.eol.product` | string | endoflife.date product slug used for the lookup (e.g. `go`, `nodejs`, `eclipse-temurin`) |
| `.lang.<language>.eol.cycle` | string | Matched release cycle (e.g. `"1.21"` for Go, `"20"` for Node.js) |
| `.lang.<language>.eol.detected_version` | string | The version read from `.lang.<language>.version` (e.g. `"1.21.5"`, `"20.11.1"`) |
| `.lang.<language>.eol.is_eol` | boolean | `true` if `eol_date` is set and is on or before today |
| `.lang.<language>.eol.is_supported` | boolean | `true` if the runtime is still in active (non-security-only) support |
| `.lang.<language>.eol.eol_date` | string \| null | ISO date when the cycle reaches end-of-life; `null` if endoflife.date does not declare one |
| `.lang.<language>.eol.support_until` | string \| null | ISO date when active support ends (security-only afterward); `null` for products that don't distinguish support from EOL |
| `.lang.<language>.eol.lts` | boolean | Whether this cycle is an LTS release (also `true` if endoflife.date returns an LTS-start date) |
| `.lang.<language>.eol.latest_in_cycle` | string | Latest patch in the cycle (e.g. `"1.21.13"`) |
| `.lang.<language>.native.endoflife.product` | string | Same as `.lang.<language>.eol.product`, kept for native-data parity |
| `.lang.<language>.native.endoflife.cycle` | object | Raw cycle object as returned by `https://endoflife.date/api/<product>.json` |

If `.lang.<language>.version` is not present (no language collector ran, or it didn't write a version) or the pinned version doesn't map to any endoflife.date cycle, nothing is written for that language. Absence of `.lang.<language>.eol` means "we couldn't determine an EOL status" — not "the runtime is supported".

## Collectors

| Collector | Description |
|-----------|-------------|
| `runtime` | For each entry in `language_products`, reads `.lang.<language>.version` from the persisted component JSON, looks up the matching cycle on endoflife.date, and writes EOL/support data per language. Code hook. |

## Installation

Add to your `lunar-config.yml`. Make sure the per-language collectors (`golang`, `nodejs`, etc.) for any language you want covered are also enabled — this collector consumes their `.lang.<lang>.version` output.

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/endoflife@v1.0.0
    on: ["domain:your-domain"]
    with:
      # Override only if you mirror the API internally
      # endoflife_base_url: "https://endoflife.date/api"
      # Override the default language → endoflife.date product map.
      # Add an entry for any new language collector you adopt.
      # language_products:
      #   go: go
      #   nodejs: nodejs
      #   python: python
      #   ruby: ruby
      #   java: amazon-corretto   # pick the JDK distribution that matches prod
      #   dotnet: dotnetfx        # use dotnetfx for legacy .NET Framework
      #   php: php
      #   rust: rust              # if/when a rust language collector lands

  # Per-language collectors populate .lang.<language>.version
  - uses: github://earthly/lunar-lib/collectors/golang@v1.0.0
  - uses: github://earthly/lunar-lib/collectors/nodejs@v1.0.0
  # ...
```

Pair it with the `endoflife` policy to enforce EOL and support guardrails:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/endoflife@v1.0.0
    enforcement: report-pr
```

No secrets are required.

### How coverage extends

Adding endoflife coverage for a new language plugin requires **no changes to this collector**:

1. The new language collector lands in lunar-lib and writes `.lang.<newlang>.version`.
2. In `lunar-config.yml`, add `<newlang>: <endoflife-product-slug>` to `language_products`.
3. On the next collection cycle, this collector reads `.lang.<newlang>.version`, queries `https://endoflife.date/api/<endoflife-product-slug>.json`, and writes `.lang.<newlang>.eol`.

If endoflife.date doesn't carry that runtime, the lookup returns 404 and nothing is written for that language — no harm done.

### Cycle matching and support semantics

Each detected version is matched to the most specific endoflife.date cycle (Go `1.21.5` → `1.21`, Node.js `20.11.1` → `20`, Python `3.11.7` → `3.11`, Ruby `3.2.0` → `3.2`, Java `17.0.9` → `17`, .NET `8.0.100` → `8`, PHP `8.2.10` → `8.2`). If no matching cycle is found (e.g. a beta/preview version not yet listed), the collector writes nothing for that language and logs a stderr message.

endoflife.date distinguishes two phases for products that have them — **active support** (the runtime is receiving normal updates including non-security fixes) and **security/maintenance** (only critical security fixes are backported). The collector exposes both as separate booleans so policies can pick the strictness they want: `is_eol` is `true` past `eol_date` (no support of any kind, including security); `is_supported` is `true` only while the runtime is in active support. For products where endoflife.date doesn't expose a separate `support` field (e.g. Go), `support_until` is `null` and `is_supported` falls back to `not is_eol`.

### Java distribution

There is no generic `java` product on endoflife.date. Pick a JDK distribution that matches your runtime: `amazon-corretto`, `azul-zulu`, `bellsoft-liberica`, `eclipse-temurin` (default), `ibm-semeru-runtime`, `microsoft-build-of-openjdk`, `oracle-jdk`, `redhat-build-of-openjdk`, `sapmachine`. These mostly track the same upstream OpenJDK release schedule but each has its own EOL/support dates, so picking the right one matters when EOL is days or weeks away. Set the `java` entry of `language_products` to your distribution.

### .NET vs .NET Framework

The default `dotnet` covers .NET 5 / 6 / 7 / 8 / 9+ (the cross-platform line). If your component is on legacy .NET Framework 4.x, set the `dotnet` entry of `language_products` to `dotnetfx`.

### Limitations and behavior notes

- **Depends on per-language collectors** — this collector reads `.lang.<lang>.version` from the persisted component JSON; it does not detect versions itself. If no language collector is configured (or none has run yet), this collector has no input and writes nothing. On a brand-new component, expect a one-cycle lag before EOL data appears: cycle 1 populates versions, cycle 2 surfaces EOL.
- **Runtime pin only** — the version this collector evaluates comes from whatever the per-language collector reported (typically a `go.mod`, `package.json`, `.python-version`, etc. pin), not the actual installed version on a deployment target.
- **Frameworks not covered** — endoflife.date covers many frameworks (Spring Boot, Django, Rails, etc.), but this v1 ships runtime-only checks.
- **No vendor-specific overrides per component** — the Java/`.NET` distribution choice is a single map applied across all components. Components on different JDKs in the same domain need separate `endoflife` collector instances.
- The collector runs on the `code` hook, so it fires on each push. The endoflife.date API is small and fast (sub-second responses).
- Network errors against endoflife.date are non-fatal: the collector logs to stderr and exits 0 without writing partial data.
- Example Component JSON is defined in `lunar-collector.yml` under `example_component_json`.
