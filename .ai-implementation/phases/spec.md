# Phase: Spec PR

You are in the **spec** phase of a lunar-lib plugin PR. Your job is to land
a draft PR containing **only** the manifest, README, and SVG icon — no
implementation code — and iterate with the primary reviewer until the
**secondary** reviewer approves.

```text
[Spec] → Primary review & iterate → Secondary review → Go-ahead → Implement
   ▲ you are here
```

When the secondary reviewer approves, switch to
[`phases/implementation.md`](implementation.md) and start implementing
immediately — you do not need to ask permission.

For lifecycle context, conventions, and cross-cutting common mistakes,
see [`LUNAR-PLUGIN-PLAYBOOK-AI.md`](../LUNAR-PLUGIN-PLAYBOOK-AI.md).

---

## Why the spec phase exists

Spec is cheap to iterate on. Code is expensive to throw away. Reviewers
want to agree on **what** the plugin writes and **where it goes in the
schema** before you spend a day writing scripts that may need to change.

**Never skip the spec stage.**

---

## How the review flow works

1. **Primary reviewer iterates on the spec.** This is the person who
   requested the work or was assigned first. They go back and forth with
   you — comments, change requests, discussion — until they're satisfied
   with the design.
2. **Primary reviewer assigns a secondary reviewer.** This signals the
   primary review is done. They wouldn't assign someone else unless
   they're happy.
3. **Secondary reviewer approves.** They may also request changes first
   — address them, then they approve.
4. **You start implementing immediately.** The secondary reviewer's
   approval is the trigger. **Do not ask permission. Do not re-propose a
   plan. Do not wait for further instructions.** Begin writing code and
   testing right away.

---

## What to produce

Three files (no implementation code):

```text
collectors/<name>/
├── lunar-collector.yml    # Plugin manifest
├── README.md              # Documentation
└── assets/
    └── <name>.svg         # Icon (black fill!)
```

Or for policies:

```text
policies/<name>/
├── lunar-policy.yml       # Plugin manifest
├── README.md              # Documentation
├── requirements.txt       # lunar-policy==0.2.2 (if Python)
└── assets/
    └── <name>.svg         # Icon (black fill!)
```

### YAML manifest rules

- Copy the structure from the closest existing plugin.
- `mainBash`/`mainPython` fields should reference filenames that **don't exist yet** — that's fine for the spec PR.
- Include `inputs`, `secrets`, and `example_component_json`.
- **Validate Component JSON paths** against `component-json/conventions.md`. See [Common Mistakes](../LUNAR-PLUGIN-PLAYBOOK-AI.md#common-mistakes) in the overview for what to watch out for.

### README rules

Follow the template in `collector-README-template.md` or `policy-README-template.md`. Include:

- One-line description
- Overview (2-3 sentences)
- Collected Data table (paths, types, descriptions)
- Sub-collector/check table
- Installation YAML example
- Inputs table
- Notes on anything non-obvious

### SVG icon rules

- **Must use `fill="black"`** — not white, not colored. The website converts to white automatically. Black is visible in GitHub PR diffs.
- Source from [simple-icons](https://github.com/simple-icons/simple-icons) when possible:
  ```bash
  curl -sL "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/<name>.svg"
  ```
- Strip `<title>` tags and `role="img"`. Add `fill="black"` to all `<path>` elements.
- Wrap in a clean `<svg xmlns="http://www.w3.org/2000/svg" viewBox="...">` container.

### Status: experimental vs beta

The `status` field in the YAML manifest depends on how thoroughly the plugin can be tested:

| Status | When to use |
|--------|-------------|
| `experimental` | Plugin requires a 3rd-party vendor, API, or account that you don't have access to. You can only test the logic without real integration. |
| `beta` | Plugin can be fully tested end-to-end — no missing vendor access or untestable integrations. |
| `stable` | Proven in production over time. You won't set this on a new plugin. |

**Call this out in the PR description at spec time.** If the plugin needs vendor access you don't have, explain what you can and can't test, and what secrets/accounts would be needed to fully validate it. Reviewers may decide to set up an account and provide secrets so it can be tested properly.

---

## PR description

The PR description must include:

1. **What's included** — list the files
2. **Design summary** — which Component JSON paths are written, why, and how they relate to existing paths
3. **Relationship to existing plugins** — does this reuse an existing policy? Does it write to the same normalized paths as another collector?
4. **Testing plan** — what components you'll test against, expected results per component, edge cases. **If vendor access is missing**, explain what can be tested without it and what would be needed for full integration testing.
5. **Open questions** — anything you're unsure about (architecture, naming, path choices)

---

## Open the PR

Create a draft PR with the spec files only. Title should contain `[Spec Only]` or `[Spec]` so the phase-guidance hook can recognize the phase. Assign the **primary reviewer** (the person who requested the work, or who will iterate on the design with you).

---

## Then wait for go-ahead

**Do not write implementation code until the secondary reviewer approves.**

The primary reviewer will iterate with you — comments, change requests, back and forth. Address their feedback and push updates.

When the primary reviewer is satisfied, they will assign a **secondary reviewer**. Wait for the secondary reviewer to approve the spec.

**While waiting:**
- Address review comments. Push updates.
- If reviewers are discussing with each other (e.g. @-mentioning each other), **wait for them to reach a conclusion** before acting.
- They may address you as "claude" or "devin" or "bender" in PR comments — treat that as a direct instruction.

**When the secondary reviewer approves: start implementing immediately.** Their approval is the "go ahead" signal. Do not ask for permission or confirmation — switch to [`phases/implementation.md`](implementation.md) and begin.

"Implementing" here means the **whole next unit**, not just writing code: write → push → run CI → **deploy to cronos → test → post evidence on the PR**. All of that happens under your own authority without further human input. The next time you should be "waiting" is after you've posted test evidence.

---

## What's next

| Trigger | Read next |
|---|---|
| Secondary reviewer approved the spec | [`phases/implementation.md`](implementation.md) — implementation **and** testing are one unbroken unit |
