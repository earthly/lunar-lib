# Python Deps CVE Probe

Block (or warn) when an agent's edit pins a Python dependency to a
version with a known critical CVE, or writes a code pattern that the
CVE exploits. Default ships the **Starlette BadHost / CVE-2026-48710**
pair; the plugin is shaped to grow per future Python-dep CVE.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It ships two probes that work together to catch BadHost-class issues
at agent-time, before the bad write lands:

- **`starlette-badhost-pin`** — hard block on dep-file edits
  (`requirements*.txt`, `pyproject.toml`, `Pipfile*`, `poetry.lock`,
  `uv.lock`) that pin Starlette to a version in `[0.8.3, 1.0.1)`.
- **`url-path-auth-pattern`** — nudge after `.py` edits that reference
  `request.url.path` inside a Starlette middleware class or function,
  pointing at `scope["path"]` as the safer alternative.

Each probe runs an independent skip-safe check script. Together they
cover the two ways the vulnerability shows up in an agent-written
diff: dragging a bad pin into the lockfile, or writing middleware
that consumes the attacker-controlled URL.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `starlette-badhost-pin`  | `agent-before-file-edit` (dep / lock files) | Hard block — proposed write pins Starlette to a BadHost-vulnerable version. |
| `url-path-auth-pattern`  | `agent-after-file-edit`  (`**/*.py`)        | Nudge — `request.url.path` used inside Starlette middleware. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so these show
up as `python-deps-cve.starlette-badhost-pin` and
`python-deps-cve.url-path-auth-pattern` in `lunar-probe logs` and PR
check titles.

> `agent-after-file-edit` is implemented today; `agent-before-file-edit`
> is the standard block hook used elsewhere in this repo (see
> [`lunar-probe` § hook types](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md)).

## The vulnerability — CVE-2026-48710 (BadHost)

Starlette **0.8.3 – 1.0.0** builds `request.url` by concatenating the
inbound `Host` header with the request path. That makes
`request.url.path` attacker-controlled: a forged `Host` value
(`Host: foo?`) can flip path boundaries and slip protected routes
past middleware that branches on `request.url.path`.

The mitigation in user code is to use `scope["path"]` instead, which
the ASGI server parses from the wire and isn't derived from a
client-supplied header. The fix landed in **Starlette 1.0.1**
(2026-05-21).

Source: [badhost.org](https://badhost.org/) ·
HN: [#48277107](https://news.ycombinator.com/item?id=48277107) ·
Starlette release: [1.0.1](https://github.com/encode/starlette/releases)

## Skip-safe behaviour

Both probes are no-ops (exit `0`, the edit proceeds) when the
vulnerability surface isn't present:

### `starlette-badhost-pin`

- The proposed write doesn't mention `starlette` at all (no pin in
  this file → nothing to check).
- The pinned version parses out as `>= 1.0.1` (already on the fix).
- The pinned version parses out as `< 0.8.3` (legacy, predates the
  Host-concatenation behaviour — separate consideration).
- The dep-file path is parseable but the resolver can't infer a
  concrete version (e.g. an open range like `starlette` with no
  operator, or a non-PyPI source). The check defers rather than
  guessing.

### `url-path-auth-pattern`

- The edited `.py` file has no Starlette imports (`from starlette`,
  `import starlette`, or `from fastapi` — FastAPI re-exports
  Starlette middleware) → it's not a Starlette app, the pattern
  doesn't apply.
- The file mentions `request.url.path` but **not** inside a
  `BaseHTTPMiddleware` subclass or an `@app.middleware(...)`-decorated
  function. Plain handler use is a separate (legitimate) case.
- The file can't be parsed as Python (syntax error, partial write).
  The check defers to `python -m py_compile` semantics rather than
  guessing.

When the trigger *is* present and none of the above apply, the probe
fires: block-tier rejects the edit with the offending line on
`{check_stdout}`; nudge-tier surfaces the message after the write
with the affected snippet.

## Installation

Prereq: [`lunar-probe`](https://github.com/earthly/lunar-probe)
installed and wired into your agent framework.

Add this probe to your `.lunar/probes.yml` (pin to the latest released
tag). The two probes are designed to ship together — they cover
different surfaces of the same CVE — but you can `include:` /
`exclude:` individually if you only want one tier:

```yaml
version: 0

probes:
  # Both tiers — recommended.
  - uses: github://earthly/lunar-lib/probes/python-deps-cve@v1.0.0

  # OR: hard block on the pin only (no `.py` nudge).
  # - uses: github://earthly/lunar-lib/probes/python-deps-cve@v1.0.0
  #   include: ["starlette-badhost-pin"]

  # OR: nudge on `.py` only (no dep-file block).
  # - uses: github://earthly/lunar-lib/probes/python-deps-cve@v1.0.0
  #   include: ["url-path-auth-pattern"]
```

See [`lunar-probe` § Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)
for the full syntax.

## Requirements

- POSIX `sh` — the check scripts are portable across Bash, dash, and
  Alpine BusyBox. No bashisms.
- `jq` on `PATH` for parsing the PreToolUse JSON payload that
  lunar-probe pipes to `check:` on stdin.
- `grep`, `sed` — BusyBox-compatible flags only (no `-P`, no
  `--include`).
- No Python runtime, no `pip`, no `ast-grep` — the checks parse what
  they need with text tooling alone, so the probe stays fast and
  dependency-light at agent-time.

## Configuration

The `starlette-badhost-pin` probe declares two inputs that let
consumers extend the same probe to a future CVE in the same package
family without forking the plugin:

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/python-deps-cve@v1.0.0
    with:
      package: starlette
      vulnerable_range: "0.8.3,1.0.1"   # min inclusive, max exclusive
```

| Input | Default | Notes |
|---|---|---|
| `package` | `starlette` | PyPI package name. |
| `vulnerable_range` | `0.8.3,1.0.1` | Comma-separated `min_inclusive,max_exclusive`. |

The `url-path-auth-pattern` probe is fixed to the BadHost surface
(`request.url.path` inside Starlette middleware) — no inputs.

> `inputs:` / `with:` are currently parsed-but-reserved in
> lunar-probe — the runner accepts them without error but doesn't yet
> dispatch consumer overrides to checks (see [`lunar-probe` §
> Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)).
> Until input dispatch ships, the check scripts run against the
> declared defaults; consumer overrides will activate automatically
> once the runner supports them, without a probe-side change.

## See also

- [`policies/python/`](../../policies/python/) — *(planned)* CI-time
  backstop policy that reads `.lang.python.dependencies[]` from the
  Python collector and flags vulnerable Starlette pins at PR-check
  time. This probe is the agent-time complement: it intercepts the
  edit before the bad pin lands; the policy catches the case where
  the pin slipped in some other way.
- [BadHost writeup](https://badhost.org/) — vulnerability details +
  proof-of-concept.
- [Starlette 1.0.1 release](https://github.com/encode/starlette/releases)
  — the fix.
