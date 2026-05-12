# ESLint Probe

Run [ESLint](https://eslint.org/) once at session end against every
JavaScript / TypeScript file the agent edited during the session.
Catches unused imports, missing returns, `no-explicit-any`, dead code,
async-without-await, and the other correctness issues ESLint configs
typically enforce.

## Overview

This is a [lunar-probe](https://github.com/earthly/lunar-probe) plugin.
It wires up a single `agent-session-end` hook with a `check_all:` batched
invocation — ESLint's cold start (Node runtime + config load) dominates
per-file cost, so batching all touched files into one `eslint` invocation
is dramatically cheaper than running once per edit.

ESLint is invoked with `--quiet` (errors only, warnings suppressed) and
**without `--fix`** — probes are read-only by design. Findings come back
to the agent as the probe `message:` body; the agent decides what to do.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `eslint.session-end` | `agent-session-end` (`**/*.{js,jsx,ts,tsx,mjs,cjs}`) | Batch-lint every JS/TS file touched in the session and surface findings. |

The probe gracefully no-ops when ESLint is not available — either
because `npx` is not on `PATH`, or because ESLint is not installed in
the consumer's `node_modules`. `npx --no-install` is used specifically
to avoid stealth-installing ESLint into the consumer's environment.

## Installation

Add to your `.lunar/probes.yml`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/eslint@main
```

Imported probes are namespaced as `eslint.<probe-name>` in
`lunar-probe logs` and other surfaces. See the
[lunar-probe plugin docs](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#probe-plugins-uses-imports)
for the full `uses:` grammar, including pinning to immutable refs and
filtering with `include:` / `exclude:`.

## Requirements

ESLint must be installed in the consumer project's `node_modules` for
this probe to do anything useful:

```sh
npm install --save-dev eslint
# or
yarn add --dev eslint
# or
pnpm add --save-dev eslint
```

The probe also relies on `npx` being on `PATH` (it ships with `npm`).
If either prerequisite is missing, the probe silently no-ops — no error,
no nudge, just nothing happens. This makes it safe to import in
mixed-project repos where some packages use ESLint and others don't.

## Related

- [`collectors/nodejs`](../../collectors/nodejs) — the CI-time companion
  that records ESLint configuration presence (`.eslintrc.*`,
  `eslint.config.*`, `package.json` `eslintConfig` block) to
  Component JSON.

The probe is the **agent-time** layer: surface findings the moment the
session ends, not after the next CI run.
