# Linear Integration — Collector Plan

A `collectors/linear` plugin to extract Linear ticket references from PR titles, validate them against the Linear GraphQL API, and detect ticket reuse across PRs. Mirrors the existing `collectors/jira` pattern.

---

## Why This Works Without a New Policy

The existing **`policies/ticket`** is already tool-agnostic — it reads from `.vcs.pr.ticket.*` (normalized paths). As long as the Linear collector writes to those same paths with `"source": {"tool": "linear", "integration": "api"}`, all six ticket policy checks (`ticket-present`, `ticket-valid`, `ticket-source`, `ticket-status`, `ticket-type`, `ticket-reuse`) work out of the box. No policy changes needed.

Users who want to enforce Linear as the required tracker can set `allowed_sources: "linear"` on the ticket policy.

---

## Component JSON Paths

The collector writes to the **same normalized paths** as the Jira collector:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.ticket.id` | string | Ticket identifier (e.g. `ENG-123`) |
| `.vcs.pr.ticket.source` | object | `{"tool": "linear", "integration": "api"}` |
| `.vcs.pr.ticket.url` | string | `https://linear.app/WORKSPACE/issue/ENG-123` |
| `.vcs.pr.ticket.valid` | boolean | Ticket exists in Linear |
| `.vcs.pr.ticket.status` | string | Workflow state name (e.g. `In Progress`, `Done`) |
| `.vcs.pr.ticket.type` | string | Label-based type or empty (Linear has no native "issue type") |
| `.vcs.pr.ticket.summary` | string | Issue title |
| `.vcs.pr.ticket.assignee` | string | Assignee email |
| `.vcs.pr.ticket.reuse_count` | number | Count of other PRs referencing the same ticket |
| `.vcs.pr.ticket.native.linear` | object | Full raw GraphQL response |

### Design Note: `type` Field

Linear doesn't have a native "issue type" concept the way Jira does (Story, Bug, Task, etc.). Options:

1. **Use the first label** — Many orgs use labels like `bug`, `feature`, `chore` as de facto types. The collector could accept an input `type_label_prefix` (e.g. `type:`) and extract matching labels.
2. **Leave empty** — If no type-like label is found, write empty string. The `ticket-type` policy will skip ("Ticket has no type information").
3. **Use priority label** — Linear has a `priorityLabel` field (`Urgent`, `High`, `Medium`, `Low`, `No priority`), but that's not really "type".

**Recommendation:** Option 1 with empty fallback. Add an input `type_labels` (comma-separated label names to treat as issue types, e.g. `bug,feature,chore,improvement`). If the issue has a matching label, write it as `.vcs.pr.ticket.type`. Otherwise leave empty.

---

## Linear GraphQL API

- **Endpoint:** `https://api.linear.app/graphql`
- **Auth:** `Authorization: <api_key>` (personal API key, no `Bearer` prefix)
- **Rate limit:** 1,500 requests/hour (complex queries cost more)

### Query: Fetch Issue by Identifier

Linear identifiers follow the pattern `TEAM-NUMBER` (e.g. `ENG-123`). The `issueSearch` query supports filtering by identifier:

```graphql
query {
  issueSearch(filter: { identifier: { eq: "ENG-123" } }, first: 1) {
    nodes {
      id
      identifier
      title
      url
      state { name type }
      assignee { email displayName }
      labels { nodes { name } }
      priority
      priorityLabel
      team { key name }
    }
  }
}
```

**curl example:**
```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: ${LINEAR_API_KEY}" \
  -d '{"query": "query($id: String!) { issueSearch(filter: { identifier: { eq: $id } }, first: 1) { nodes { id identifier title url state { name type } assignee { email displayName } labels { nodes { name } } priority priorityLabel team { key name } } } }", "variables": {"id": "ENG-123"}}'
```

**Response shape:**
```json
{
  "data": {
    "issueSearch": {
      "nodes": [
        {
          "id": "uuid",
          "identifier": "ENG-123",
          "title": "Add payment validation",
          "url": "https://linear.app/acme/issue/ENG-123/add-payment-validation",
          "state": { "name": "In Progress", "type": "started" },
          "assignee": { "email": "jane@acme.com", "displayName": "Jane" },
          "labels": { "nodes": [{ "name": "bug" }, { "name": "backend" }] },
          "priority": 2,
          "priorityLabel": "High",
          "team": { "key": "ENG", "name": "Engineering" }
        }
      ]
    }
  }
}
```

---

## Collector Plugin: `collectors/linear`

### File Structure

```
collectors/linear/
├── assets/
│   └── linear.svg          # Linear logo (black fill)
├── helpers.sh               # Shared: PR title fetch + ticket ID extraction (same as Jira)
├── ticket.sh                # Sub-collector: extract + validate via Linear API
├── ticket-history.sh        # Sub-collector: ticket reuse count via Lunar SQL
├── lunar-collector.yml      # Plugin manifest
└── README.md
```

### `lunar-collector.yml`

```yaml
version: 0

name: linear
description: Collect Linear ticket metadata from PR titles and validate against Linear API
author: support@earthly.dev

default_image: earthly/lunar-lib:base-main

landing_page:
  display_name: "Linear Collector"
  long_description: |
    Extract Linear ticket references from pull request titles, validate them
    against the Linear GraphQL API, and detect ticket reuse across PRs.
  categories: ["vcs"]
  icon: "assets/linear.svg"
  status: "stable"
  related:
    - slug: "ticket"
      type: "policy"
      reason: "Enforces ticket presence, validity, status, type, and reuse limits"

collectors:
  - name: ticket
    description: |
      Extracts Linear ticket ID from PR title, fetches issue metadata from
      the Linear GraphQL API, and writes normalized ticket data to
      .vcs.pr.ticket and native Linear data to .vcs.pr.ticket.native.linear.
    mainBash: ticket.sh
    runs_on: [prs]
    hook:
      type: code
    keywords: ["linear", "ticket", "pr", "issue tracking"]

  - name: ticket-history
    description: |
      Queries the Lunar SQL database to count how many other PRs reference
      the same ticket. Writes .vcs.pr.ticket.reuse_count for policy
      evaluation. Detects ticket recycling abuse.
    mainBash: ticket-history.sh
    runs_on: [prs]
    hook:
      type: code
    keywords: ["linear", "ticket reuse", "compliance", "audit"]

inputs:
  ticket_prefix:
    description: Character(s) before the ticket ID in PR titles (empty = match anywhere)
    default: ""
  ticket_suffix:
    description: Character(s) after the ticket ID in PR titles (empty = match anywhere)
    default: ""
  ticket_pattern:
    description: Regex pattern for ticket ID (without prefix/suffix)
    default: "[A-Za-z][A-Za-z0-9]+-[0-9]+"
  type_labels:
    description: >
      Comma-separated label names to treat as issue types (e.g. "bug,feature,chore").
      If the Linear issue has a matching label, it's written as .vcs.pr.ticket.type.
      Empty = don't extract type from labels.
    default: ""

secrets:
  LINEAR_API_KEY:
    description: Linear personal API key for authentication
  GH_TOKEN:
    description: GitHub token for reading PR metadata

example_component_json: |
  {
    "vcs": {
      "pr": {
        "ticket": {
          "id": "ENG-123",
          "source": { "tool": "linear", "integration": "api" },
          "url": "https://linear.app/acme/issue/ENG-123/add-payment-validation",
          "valid": true,
          "status": "In Progress",
          "type": "bug",
          "summary": "Add payment validation",
          "assignee": "jane@acme.com",
          "reuse_count": 0,
          "native": {
            "linear": { "...full Linear GraphQL response..." }
          }
        }
      }
    }
  }
```

### `helpers.sh`

Identical to `collectors/jira/helpers.sh` — the ticket extraction logic (regex from PR title) and PR title fetch (GitHub API) are the same. **Copy it directly** or factor into a shared location later.

### `ticket.sh`

```bash
#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Only run in PR context.
if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a PR context, skipping." >&2
  exit 0
fi

# Require GH_TOKEN to fetch PR title.
if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "Linear collector requires GH_TOKEN secret to query GitHub." >&2
  exit 0
fi

# Fetch PR title from GitHub.
PR_TITLE="$(fetch_pr_title)" || exit 0

# Extract ticket ID from PR title.
TICKET_KEY="$(extract_ticket_id "$PR_TITLE")" || exit 0

if [ -z "$TICKET_KEY" ]; then
  exit 0
fi

# Write the ticket ID and source regardless of Linear API result.
lunar collect ".vcs.pr.ticket.id" "$TICKET_KEY"
jq -n '{"tool": "linear", "integration": "api"}' | lunar collect -j ".vcs.pr.ticket.source" -

# Validate required Linear API configuration.
if [ -z "${LUNAR_SECRET_LINEAR_API_KEY:-}" ]; then
  echo "LINEAR_API_KEY secret not set, skipping Linear API validation." >&2
  exit 0
fi

# Build GraphQL query.
QUERY='query($identifier: String!) {
  issueSearch(filter: { identifier: { eq: $identifier } }, first: 1) {
    nodes {
      id identifier title url
      state { name type }
      assignee { email displayName }
      labels { nodes { name } }
      priority priorityLabel
      team { key name }
    }
  }
}'

PAYLOAD=$(jq -n --arg q "$QUERY" --arg id "$TICKET_KEY" \
  '{"query": $q, "variables": {"identifier": $id}}')

set +e
RESPONSE=$(curl -fsS -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: ${LUNAR_SECRET_LINEAR_API_KEY}" \
  -d "$PAYLOAD")
CURL_STATUS=$?
set -e

if [ $CURL_STATUS -ne 0 ] || [ -z "$RESPONSE" ]; then
  echo "Unable to query Linear API for ticket ${TICKET_KEY}." >&2
  exit 0
fi

# Check if we got a result.
NODE=$(echo "$RESPONSE" | jq -r '.data.issueSearch.nodes[0] // empty')
if [ -z "$NODE" ] || [ "$NODE" = "null" ]; then
  echo "Ticket ${TICKET_KEY} not found in Linear." >&2
  exit 0
fi

# Ticket exists — write normalized fields.
lunar collect -j ".vcs.pr.ticket.valid" true

TICKET_URL=$(echo "$NODE" | jq -r '.url // empty')
TICKET_STATUS=$(echo "$NODE" | jq -r '.state.name // empty')
TICKET_SUMMARY=$(echo "$NODE" | jq -r '.title // empty')
TICKET_ASSIGNEE=$(echo "$NODE" | jq -r '.assignee.email // empty')

[ -n "$TICKET_URL" ] && lunar collect ".vcs.pr.ticket.url" "$TICKET_URL"
lunar collect \
  ".vcs.pr.ticket.status" "$TICKET_STATUS" \
  ".vcs.pr.ticket.summary" "$TICKET_SUMMARY" \
  ".vcs.pr.ticket.assignee" "$TICKET_ASSIGNEE"

# Extract type from labels if configured.
TYPE_LABELS="${LUNAR_VAR_TYPE_LABELS:-}"
if [ -n "$TYPE_LABELS" ]; then
  # Get all label names from the issue.
  ISSUE_LABELS=$(echo "$NODE" | jq -r '.labels.nodes[].name' 2>/dev/null)

  # Check each configured type label against issue labels.
  IFS=',' read -ra TYPES <<< "$TYPE_LABELS"
  for t in "${TYPES[@]}"; do
    t=$(echo "$t" | xargs)  # trim whitespace
    if echo "$ISSUE_LABELS" | grep -qix "$t"; then
      lunar collect ".vcs.pr.ticket.type" "$t"
      break
    fi
  done
fi

# Write full raw response under native.linear.
echo "$NODE" | lunar collect -j ".vcs.pr.ticket.native.linear" -
```

### `ticket-history.sh`

Identical to `collectors/jira/ticket-history.sh` — the SQL query checks `.vcs.pr.ticket.id` in the merged component JSON, which is the same path regardless of whether the ticket came from Jira or Linear. **Copy directly.**

---

## SVG Icon

The Linear logo should use `fill="black"` per lunar-lib conventions. A simple Linear logomark:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <path fill="black" d="M1.225 61.127c-.26-.754-.26-1.504 0-2.251l17.26-44.917A3.221 3.221 0 0 1 21.48 12h57.04c1.753 0 3.226 1.126 3.226 2.5V42.3L28.3 95.747a3.221 3.221 0 0 1-2.996 1.96c-.905 0-1.754-.38-2.362-1.04L1.225 61.127Z"/>
  <path fill="black" d="M81.746 42.3V14.5c0-1.374 1.473-2.5 3.226-2.5h3.548c1.753 0 3.48 1.126 3.48 2.5v71c0 1.374-1.727 2.5-3.48 2.5H47.654L81.746 42.3Z"/>
</svg>
```

> **Note:** The actual Linear logo SVG should be sourced from Linear's brand assets. The above is a placeholder — verify the real logomark before committing.

---

## Installation Example

```yaml
# lunar-config.yml
collectors:
  - uses: github://earthly/lunar-lib/collectors/linear
    on: ["domain:your-domain"]
    with:
      type_labels: "bug,feature,chore,improvement"

policies:
  - uses: github://earthly/lunar-lib/policies/ticket
    on: ["domain:your-domain"]
    with:
      allowed_sources: "linear"
      allowed_statuses: "In Progress,In Review,Done"
      disallowed_statuses: "Cancelled,Duplicate"
      allowed_types: "bug,feature,chore"
      max_ticket_reuse: "3"
```

Required secrets:
- `LINEAR_API_KEY` — Linear personal API key (Settings → API → Personal API keys)
- `GH_TOKEN` — GitHub token for reading PR metadata

---

## Implementation Notes

### Shared Code with Jira

`helpers.sh` (PR title fetch + ticket ID extraction) is identical between Jira and Linear. For now, copy the file. If a third issue tracker is added, factor it into a shared library.

### Alpine/BusyBox Compatibility

The collector runs on `earthly/lunar-lib:base-main` (Alpine). Key considerations:
- `jq` is available in the base image — needed for GraphQL payload construction and response parsing
- `curl` is available — needed for the Linear API call
- `grep -qix` works on BusyBox for case-insensitive exact match
- `IFS=',' read -ra` works in bash (the image has bash)

### Linear API Key Scope

A Linear personal API key grants read access to all data the user can see. For this collector, the minimum needed is:
- Read issues (to validate ticket existence and fetch metadata)
- No write access needed

Recommend users create a dedicated "service account" or use a workspace-wide API key if available.

### Ticket ID Pattern

The default regex `[A-Za-z][A-Za-z0-9]+-[0-9]+` matches both Jira (`ABC-123`) and Linear (`ENG-123`) formats since they use the same pattern. Users who have both Jira and Linear can differentiate via:
- Separate `ticket_prefix`/`ticket_suffix` patterns
- Or by running only one collector per domain

---

## Testing Plan

### Local Testing

```bash
# From a component directory with PRs
cd /home/brandon/code/earthly/pantalasa-cronos/backend

# Test ticket extraction
LUNAR_COMPONENT_PR=1 \
LUNAR_COMPONENT_ID=github.com/pantalasa-cronos/backend \
LUNAR_SECRET_GH_TOKEN=<token> \
LUNAR_SECRET_LINEAR_API_KEY=<key> \
bash /path/to/collectors/linear/ticket.sh
```

### Expected Results

| Scenario | Expected Outcome |
|----------|-----------------|
| PR title `[ENG-123] Fix bug` with valid Linear ticket | `ticket.id=ENG-123`, `valid=true`, status/summary/assignee populated |
| PR title `[ENG-999] Fix bug` with non-existent ticket | `ticket.id=ENG-999`, no `valid` field (API returned nothing) |
| PR title `Fix bug` (no ticket reference) | No data written, exit 0 |
| `LINEAR_API_KEY` not set | Writes `ticket.id` and `source` only, skips validation |
| PR with ticket reused 5 times, `max_ticket_reuse=3` | `ticket-reuse` policy → FAIL |

### Edge Cases to Verify

1. **Linear issue with no assignee** — `assignee` field should be empty string, not crash
2. **Linear issue with no labels + `type_labels` configured** — `type` field not written, `ticket-type` policy skips
3. **GraphQL error response** (invalid API key) — Should log error and exit 0 gracefully

---

## Questions for Review

1. **`type_labels` input** — Is the label-matching approach for issue types good enough, or should we expose Linear's priority as type instead? Linear doesn't have a native type field.
2. **Shared `helpers.sh`** — Copy for now, or immediately factor into a shared location (e.g. `collectors/_shared/ticket-helpers.sh`)?
3. **Workspace URL** — Linear ticket URLs include the workspace slug (e.g. `https://linear.app/acme/issue/ENG-123`). The GraphQL response includes the full `url` field, so we don't need users to configure this. But if the API is unreachable, we can't construct the URL. Should we add an optional `linear_workspace` input for URL construction fallback (like Jira's `jira_base_url`)?
4. **Ticket policy updates** — The `ticket-present` policy currently says "PRs should reference a Jira ticket" in its description. Should we make it generic ("PRs should reference an issue tracker ticket") since the policy is already tool-agnostic?
