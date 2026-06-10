"""Reusable webhook-alert helper for Lunar policies.

Defines a *standard* JSON payload schema for policy alerts plus a best-effort
HTTP POST that never raises and never blocks for long. It is deliberately
dependency-free (Python stdlib only) so any policy can reuse it without adding
to ``requirements.txt``.

Design contract (so both policies and downstream consumers can rely on it):

  * A policy builds a payload with :func:`build_payload` and sends it with
    :func:`post_webhook`.
  * :func:`post_webhook` returns a ``(sent, detail)`` tuple and swallows *all*
    network errors. Alerting is best-effort: a slow or dead endpoint must never
    flip a policy result or add unbounded latency to a policy run.
  * Every payload carries a ``dedupe_key`` derived from stable content
    (component + git sha + the set of finding ids). Re-running the same policy
    on the same commit yields the *same* key, so consumers can drop duplicates.
    ``timestamp`` is informational and is intentionally excluded from the key.

Payload schema (``schema_version`` 1)::

    {
      "schema_version": 1,
      "policy": "sca",
      "component": "github.com/acme/api",
      "git_sha": "abc123",          # "" if unavailable
      "run_id": "abc123",           # currently the git sha; stable per commit
      "dedupe_key": "9f86d081...",  # stable hash; safe to dedupe on
      "timestamp": "2026-06-10T12:34:56Z",
      "findings": [
        {"id": "CVE-2023-44487", "severity": "high",
         "package": "golang.org/x/net", "fix_version": "0.17.0"}
      ],
      "summary": {"total": 1, "by_severity": {"critical": 0, "high": 1, ...}}
    }
"""

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

SCHEMA_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = 2.0


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dedupe_key(component, git_sha, finding_ids):
    """Return a stable idempotency key for a (component, commit, finding-set).

    The timestamp is deliberately excluded: re-runs of the same commit produce
    the same key so downstream consumers can suppress duplicate alerts. The id
    set is sorted so finding order does not affect the key.
    """
    ids = ",".join(sorted(str(i) for i in finding_ids))
    raw = f"{component}\x1f{git_sha}\x1f{ids}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_payload(policy, findings, component=None, git_sha=None, summary=None, timestamp=None):
    """Build the standard alert payload.

    ``findings`` is a list of dicts already normalized to
    ``{id, severity, package, fix_version}``. ``component`` and ``git_sha``
    default to the ``LUNAR_*`` runtime environment variables when not provided.
    """
    if component is None:
        component = os.environ.get("LUNAR_COMPONENT_ID", "")
    if git_sha is None:
        git_sha = os.environ.get("LUNAR_COMPONENT_GIT_SHA", "")

    finding_ids = [f.get("id") for f in findings if f.get("id")]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "policy": policy,
        "component": component,
        "git_sha": git_sha,
        # No dedicated run id is exposed to policies at runtime, so we key the
        # run on the commit being evaluated. It is stable across re-runs.
        "run_id": git_sha or "",
        "dedupe_key": dedupe_key(component, git_sha, finding_ids),
        "timestamp": timestamp or _now_iso(),
        "findings": findings,
    }
    if summary is not None:
        payload["summary"] = summary
    return payload


def post_webhook(url, payload, timeout=DEFAULT_TIMEOUT_SECONDS, auth_token=None):
    """POST ``payload`` as JSON to ``url``. Best-effort: never raises.

    Returns ``(sent, detail)`` where ``sent`` is True only on a 2xx response.
    A short ``timeout`` bounds the latency added to a policy run. Any failure
    (timeout, DNS error, connection refused, non-2xx) is swallowed and reported
    in ``detail`` so the caller can log it without failing the check.
    """
    if not url:
        return (False, "no url")
    try:
        body = json.dumps(payload).encode("utf-8")
    except (TypeError, ValueError) as e:
        return (False, f"payload not serializable: {e}")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", f"lunar-policy-webhook/{SCHEMA_VERSION}")
    if auth_token:
        req.add_header("Authorization", f"Bearer {auth_token}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            if 200 <= code < 300:
                return (True, f"HTTP {code}")
            return (False, f"HTTP {code}")
    except urllib.error.HTTPError as e:
        return (False, f"HTTP {e.code}")
    except Exception as e:  # noqa: BLE001 - best-effort notifier: swallow everything
        # Intentionally broad: a notifier must never propagate a network error
        # into the policy result. The failure is reported via the return value.
        return (False, f"{type(e).__name__}: {e}")
