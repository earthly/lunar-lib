"""Unit tests for the SCA webhook alert notifier (alert.py) and the reusable
webhook helper (webhook.py).

Run from this directory:
    python3 -m unittest test_webhook_alert -v

The alert tests spin up a throwaway HTTP receiver on localhost to prove the
webhook fires with the right payload, and that a slow or dead endpoint never
fails the check (alerting is best-effort).
"""

import contextlib
import io
import json
import os
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import Node, CheckStatus  # noqa: E402

import webhook  # noqa: E402
import alert  # noqa: E402


# --------------------------------------------------------------------------- #
# Mock webhook receiver                                                        #
# --------------------------------------------------------------------------- #


class Receiver:
    """A throwaway localhost HTTP server that records POSTed requests."""

    def __init__(self, status=200, delay=0.0):
        self.requests = []  # list of (headers: dict, body: parsed-json-or-None)
        self._status = status
        self._delay = delay
        recv = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if recv._delay:
                    time.sleep(recv._delay)
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = None
                recv.requests.append((dict(self.headers), body))
                self.send_response(recv._status)
                self.end_headers()

            def log_message(self, *args):  # silence the default stderr logging
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._server.server_port}/hook"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


# A port that (almost certainly) has nothing listening, for the "endpoint
# down" path. urllib gets ECONNREFUSED fast.
DEAD_URL = "http://127.0.0.1:9/hook"


# --------------------------------------------------------------------------- #
# Component JSON fixtures                                                      #
# --------------------------------------------------------------------------- #


def node(sca=None, lang=True):
    """Build a policy node mirroring production policy-eval (workflows done)."""
    data = {}
    if lang:
        data["lang"] = {"go": {"version": "1.22"}}
    if sca is not None:
        data["sca"] = sca
    return Node.from_component_json(data, bundle_info={"workflows_finished": True})


SCA_WITH_HIGH = {
    "source": {"tool": "trivy", "integration": "code"},
    "vulnerabilities": {"critical": 0, "high": 2, "medium": 1, "low": 0, "total": 3},
    "findings": [
        {"severity": "high", "package": "golang.org/x/net", "version": "0.7.0",
         "ecosystem": "gomod", "cve": "CVE-2023-44487", "fix_version": "0.17.0", "fixable": True},
        {"severity": "high", "package": "github.com/foo/bar", "version": "1.0.0",
         "ecosystem": "gomod", "cve": "CVE-2024-0001", "fix_version": None, "fixable": False},
        {"severity": "medium", "package": "baz", "version": "2.0.0",
         "ecosystem": "gomod", "cve": "CVE-2024-0002", "fix_version": "2.0.1", "fixable": True},
    ],
    "summary": {"has_critical": False, "has_high": True, "all_fixable": False},
}

SCA_CLEAN = {
    "source": {"tool": "trivy", "integration": "code"},
    "vulnerabilities": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
    "findings": [],
    "summary": {"has_critical": False, "has_high": False, "all_fixable": True},
}

SCA_SUMMARY_ONLY = {  # a collector that reports counts but no per-finding detail
    "source": {"tool": "snyk", "integration": "github_app"},
    "vulnerabilities": {"critical": 1, "high": 3, "medium": 0, "low": 0, "total": 4},
    "summary": {"has_critical": True, "has_high": True},
}


# --------------------------------------------------------------------------- #
# Env isolation + run helpers                                                  #
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def lunar_env(**overrides):
    """Strip all LUNAR_* env, set component identity + overrides, then restore.

    Prevents LUNAR_VAR_* / LUNAR_SECRET_* leaking between tests (variable()
    scans the whole environment by prefix).
    """
    saved = {k: v for k, v in os.environ.items() if k.startswith("LUNAR_")}
    for k in list(os.environ):
        if k.startswith("LUNAR_"):
            del os.environ[k]
    os.environ["LUNAR_COMPONENT_ID"] = "github.com/acme/api"
    os.environ["LUNAR_COMPONENT_GIT_SHA"] = "abc123"
    os.environ.update(overrides)
    try:
        yield
    finally:
        for k in list(os.environ):
            if k.startswith("LUNAR_"):
                del os.environ[k]
        os.environ.update(saved)


def run_alert(n, **env):
    """Run alert.main with the given LUNAR_* env, swallowing the SDK's stdout."""
    with lunar_env(**env):
        with contextlib.redirect_stdout(io.StringIO()):
            return alert.main(node=n)


def resolved_status(c):
    """Resolve a check to PASS/FAIL/SKIPPED.

    The SDK's Check.status property aggregates FAIL/ERROR/PENDING but reports a
    skipped check as PASS, while the real runtime still receives the SKIPPED
    result. Detect the skip from the emitted result set, mirroring the runtime.
    """
    for r in getattr(c, "_results", []):
        if r.result == CheckStatus.SKIPPED:
            return CheckStatus.SKIPPED
    return c.status


def skip_reason(c):
    """Return the skip/failure message recorded on the check, if any."""
    for r in getattr(c, "_results", []):
        if r.failure_message:
            return r.failure_message
    return None


# --------------------------------------------------------------------------- #
# webhook.py helper tests                                                      #
# --------------------------------------------------------------------------- #


class WebhookHelperTests(unittest.TestCase):
    def test_dedupe_key_is_order_independent(self):
        a = webhook.dedupe_key("c", "sha", ["CVE-2", "CVE-1"])
        b = webhook.dedupe_key("c", "sha", ["CVE-1", "CVE-2"])
        self.assertEqual(a, b)

    def test_dedupe_key_changes_with_content(self):
        a = webhook.dedupe_key("c", "sha", ["CVE-1"])
        b = webhook.dedupe_key("c", "sha", ["CVE-1", "CVE-2"])
        self.assertNotEqual(a, b)

    def test_build_payload_shape_and_stable_key(self):
        findings = [{"id": "CVE-1", "severity": "high", "package": "p", "fix_version": "1.0"}]
        p1 = webhook.build_payload("sca", findings, component="c", git_sha="sha", timestamp="T1")
        p2 = webhook.build_payload("sca", findings, component="c", git_sha="sha", timestamp="T2")
        self.assertEqual(p1["schema_version"], webhook.SCHEMA_VERSION)
        self.assertEqual(p1["policy"], "sca")
        self.assertEqual(p1["component"], "c")
        self.assertEqual(p1["git_sha"], "sha")
        self.assertEqual(p1["run_id"], "sha")
        self.assertEqual(p1["findings"], findings)
        # Timestamp is informational; the dedupe key must be stable across runs.
        self.assertNotEqual(p1["timestamp"], p2["timestamp"])
        self.assertEqual(p1["dedupe_key"], p2["dedupe_key"])

    def test_post_webhook_success_round_trip(self):
        with Receiver(status=200) as r:
            sent, detail = webhook.post_webhook(r.url, {"hello": "world"}, timeout=2)
        self.assertTrue(sent)
        self.assertEqual(detail, "HTTP 200")
        self.assertEqual(len(r.requests), 1)
        headers, body = r.requests[0]
        self.assertEqual(body, {"hello": "world"})
        self.assertEqual(headers.get("Content-Type"), "application/json")

    def test_post_webhook_non_2xx_is_not_an_error(self):
        with Receiver(status=500) as r:
            sent, detail = webhook.post_webhook(r.url, {"x": 1}, timeout=2)
        self.assertFalse(sent)
        self.assertEqual(detail, "HTTP 500")

    def test_post_webhook_connection_refused_never_raises(self):
        sent, detail = webhook.post_webhook(DEAD_URL, {"x": 1}, timeout=1)
        self.assertFalse(sent)
        self.assertTrue(detail)  # some diagnostic string, but no exception

    def test_post_webhook_timeout_is_bounded(self):
        with Receiver(status=200, delay=1.0) as r:
            start = time.monotonic()
            sent, detail = webhook.post_webhook(r.url, {"x": 1}, timeout=0.2)
            elapsed = time.monotonic() - start
        self.assertFalse(sent)
        self.assertLess(elapsed, 0.9)  # aborted at the timeout, well before 1.0s

    def test_post_webhook_empty_url(self):
        sent, detail = webhook.post_webhook("", {"x": 1})
        self.assertFalse(sent)
        self.assertEqual(detail, "no url")

    def test_post_webhook_forwards_auth_header(self):
        with Receiver(status=200) as r:
            webhook.post_webhook(r.url, {"x": 1}, timeout=2, auth_token="s3cr3t")
        headers, _ = r.requests[0]
        self.assertEqual(headers.get("Authorization"), "Bearer s3cr3t")


# --------------------------------------------------------------------------- #
# alert.py notifier tests                                                      #
# --------------------------------------------------------------------------- #


class AlertCheckTests(unittest.TestCase):
    def test_skips_when_no_language(self):
        with Receiver() as r:
            c = run_alert(node(sca=SCA_WITH_HIGH, lang=False), LUNAR_VAR_alert_url=r.url)
            self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
            self.assertEqual(len(r.requests), 0)

    def test_skips_when_alert_url_unset(self):
        # No LUNAR_VAR_alert_url at all -> alerting disabled, zero network cost.
        c = run_alert(node(sca=SCA_WITH_HIGH))
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)

    def test_skips_when_no_sca_data(self):
        with Receiver() as r:
            c = run_alert(node(sca=None), LUNAR_VAR_alert_url=r.url)
            self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
            self.assertEqual(len(r.requests), 0)

    def test_skips_when_summary_only_collector(self):
        with Receiver() as r:
            c = run_alert(node(sca=SCA_SUMMARY_ONLY), LUNAR_VAR_alert_url=r.url)
            self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
            self.assertEqual(len(r.requests), 0)

    def test_skips_when_no_findings_at_or_above_threshold(self):
        with Receiver() as r:
            c = run_alert(node(sca=SCA_CLEAN), LUNAR_VAR_alert_url=r.url)
            self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
            self.assertEqual(len(r.requests), 0)

    def test_fires_with_findings_and_correct_payload(self):
        with Receiver(status=200) as r:
            c = run_alert(
                node(sca=SCA_WITH_HIGH),
                LUNAR_VAR_alert_url=r.url,
                LUNAR_VAR_min_severity="high",
            )
        self.assertEqual(resolved_status(c), CheckStatus.PASS)
        self.assertEqual(len(r.requests), 1)
        _, body = r.requests[0]
        self.assertEqual(body["policy"], "sca")
        self.assertEqual(body["component"], "github.com/acme/api")
        self.assertEqual(body["git_sha"], "abc123")
        self.assertEqual(body["run_id"], "abc123")
        self.assertEqual(body["schema_version"], 1)
        self.assertIn("dedupe_key", body)
        self.assertIn("timestamp", body)
        # min_severity=high -> only the two HIGH findings, medium excluded.
        ids = sorted(f["id"] for f in body["findings"])
        self.assertEqual(ids, ["CVE-2023-44487", "CVE-2024-0001"])
        for f in body["findings"]:
            self.assertEqual(set(f.keys()), {"id", "severity", "package", "fix_version"})
        self.assertEqual(body["summary"]["total"], 2)
        self.assertEqual(body["summary"]["by_severity"]["high"], 2)

    def test_min_severity_widens_finding_set(self):
        with Receiver(status=200) as r:
            run_alert(
                node(sca=SCA_WITH_HIGH),
                LUNAR_VAR_alert_url=r.url,
                LUNAR_VAR_min_severity="medium",
            )
            _, body = r.requests[0]
        self.assertEqual(body["summary"]["total"], 3)  # 2 high + 1 medium

    def test_critical_threshold_finds_nothing_and_skips(self):
        with Receiver() as r:
            c = run_alert(
                node(sca=SCA_WITH_HIGH),
                LUNAR_VAR_alert_url=r.url,
                LUNAR_VAR_min_severity="critical",
            )
            self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
            self.assertEqual(len(r.requests), 0)

    def test_never_fails_when_endpoint_is_down(self):
        # Endpoint refuses the connection: the check must NOT fail. It surfaces
        # the non-delivery as a non-gating SKIP with a reason.
        c = run_alert(
            node(sca=SCA_WITH_HIGH),
            LUNAR_VAR_alert_url=DEAD_URL,
            LUNAR_VAR_alert_timeout="1",
        )
        self.assertNotEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
        self.assertIn("not delivered", skip_reason(c).lower())

    def test_never_fails_when_endpoint_is_slow(self):
        with Receiver(status=200, delay=1.0) as r:
            start = time.monotonic()
            c = run_alert(
                node(sca=SCA_WITH_HIGH),
                LUNAR_VAR_alert_url=r.url,
                LUNAR_VAR_alert_timeout="0.2",
            )
            elapsed = time.monotonic() - start
        self.assertNotEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
        self.assertLess(elapsed, 0.9)  # bounded by the timeout, not the 1.0s delay

    def test_delivery_failure_skips_with_reason_never_fails(self):
        # Endpoint reachable but returns 500: POST is attempted, the check
        # surfaces a non-gating SKIP carrying the HTTP status, and never fails.
        with Receiver(status=500) as r:
            c = run_alert(node(sca=SCA_WITH_HIGH), LUNAR_VAR_alert_url=r.url)
            self.assertEqual(len(r.requests), 1)  # delivery was attempted
        self.assertNotEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
        self.assertIn("HTTP 500", skip_reason(c))

    def test_auth_token_from_secret_is_forwarded(self):
        with Receiver(status=200) as r:
            run_alert(
                node(sca=SCA_WITH_HIGH),
                LUNAR_VAR_alert_url=r.url,
                LUNAR_SECRET_ALERT_AUTH_TOKEN="topsecret",
            )
            headers, _ = r.requests[0]
        self.assertEqual(headers.get("Authorization"), "Bearer topsecret")


if __name__ == "__main__":
    unittest.main(verbosity=2)
