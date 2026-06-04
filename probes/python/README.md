# Python Probe

Agent-time guardrails for Python projects, shipped as a single
[`lunar-probe`](https://github.com/earthly/lunar-probe) plugin. Each
capability is a separate probe; select the ones you want with `include:` /
`exclude:` on the `uses:` entry — mirroring how
[`policies/python/`](../../policies/python/) groups Python CI-time
policies under one plugin.

## Probes

| Name | Hook | What it does | Details |
|------|------|--------------|---------|
| `disallowed-deps` | `agent-before-file-edit` | Block dep / lock edits that pin a package to a known-vulnerable version. | [docs](docs/disallowed-deps.md) |

Probes auto-namespace as `python.<probe>` at runtime (e.g.
`python.disallowed-deps`) — visible in `lunar-probe logs` and PR check
titles. More Python probes (a linter, a CVE code-pattern nudge, …) land
under this plugin via separate PRs; each adds a row above and its own page
under [`docs/`](docs/).

## Installation

Prereq: [`lunar-probe`](https://github.com/earthly/lunar-probe) installed
and wired into your agent framework.

Add to your `.lunar/probes.yml` (pin to a released tag) and select the
probes you want with `include:`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0
    include: ["disallowed-deps"]
```

Omit `include:` to opt into every probe the plugin ships, or use
`exclude:` to take all-but-one. See
[`lunar-probe` § Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)
for the full syntax.

## See also

- [`policies/python/`](../../policies/python/) — CI-time Python policies.
  The agent-time probes here are the edit-time complement: they intercept
  a problem before the edit lands, the policies catch it at PR-check time.
