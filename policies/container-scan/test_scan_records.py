"""Unit tests for judging container scans per record (helpers.scan_snapshots).

Run from this directory:
    python3 -m unittest test_scan_records -v

The hub hands a policy two views of a commit: the merged blob, which on the
default branch also folds in the latest scheduled rescan from whatever commit
it ran at, and the records collected at the commit itself
(`metadata_instances`). These tests build both the way the hub does and check
that max-severity and unfixable-reviewed judge the commit's own scans.
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import CheckStatus, Node  # noqa: E402

import max_severity  # noqa: E402
import unfixable_reviewed  # noqa: E402
from helpers import scan_snapshots  # noqa: E402
from test_max_severity import failure_message, lunar_env, resolved_status  # noqa: E402

OLD, NEW = "5d0b0528", "1b310193"
HUB_OLD, HUB_NEW = f"earthly/lunar-hub:{OLD}", f"earthly/lunar-hub:{NEW}"
SCRIPTS = "earthly/lunar-scripts:main-alpine"  # a moving tag, same name in every scan

CONTAINERS = {"containers": {"native": {"docker": {"cicd": {"cmds": [
    {"cmd": f"docker push {HUB_NEW}"},
    {"cmd": f"docker push {SCRIPTS}"},
]}}}}}

X_NET = "CVE-2026-78661"


def finding(cve, image, severity="high", fix="0.62.0", package="golang.org/x/net"):
    return {"severity": severity, "package": package, "version": "v0.60.0", "cve": cve,
            "fix_version": fix, "fixable": fix is not None, "image": image}


def scan(tool, integration, sha, at, images, findings=(), errors=None):
    """A `.container_scan` payload as the trivy/grype container sub-collectors write it."""
    def counts(fs):
        return {s: sum(1 for f in fs if f["severity"] == s) for s in ("critical", "high", "medium", "low")} | {
            "total": len(fs)}

    def summary(fs):
        return {"has_critical": any(f["severity"] == "critical" for f in fs),
                "has_high": any(f["severity"] == "high" for f in fs),
                "all_fixable": all(f["fixable"] for f in fs)}

    payload = {
        "source": {"tool": tool, "integration": integration, "collected_at": at, "collected_sha": sha},
        "image": images[-1],
        "images": [{"image": i, "tool": tool, "digest": f"sha256:{'0' * 63}{n}",
                    "vulnerabilities": counts([f for f in findings if f["image"] == i]),
                    "summary": summary([f for f in findings if f["image"] == i])}
                   for n, i in enumerate(images)],
        "vulnerabilities": counts(findings),
        "summary": summary(findings),
    }
    if findings:
        payload["findings"] = list(findings)
    if errors:
        payload["errors"] = errors
    return payload


def unfixable(image, cve="CVE-2026-41567", package="stdlib"):
    return finding(cve, image, fix=None, package=package)


# The 5.0.0 release shape: the 03:03 Trivy rescan of the previous commit's images
# still saw the x/net CVE; the on-push scans of the release commit did not.
STALE_TRIVY_CRON = scan("trivy", "cron", OLD, "2026-11-11T03:03:38Z", [HUB_OLD, SCRIPTS],
                        [finding(X_NET, HUB_OLD), finding(X_NET, SCRIPTS), unfixable(HUB_OLD)])
STALE_GRYPE_CRON = scan("grype", "cron", OLD, "2026-11-11T03:12:23Z", [HUB_OLD, SCRIPTS],
                        [unfixable(HUB_OLD)])
FRESH_TRIVY = scan("trivy", "after-json", NEW, "2026-11-11T05:27:02Z", [HUB_NEW, SCRIPTS],
                   [unfixable(HUB_NEW), unfixable(SCRIPTS)])
FRESH_GRYPE = scan("grype", "after-json", NEW, "2026-11-11T05:28:00Z", [HUB_NEW, SCRIPTS],
                   [unfixable(HUB_NEW)])


def hub_merge(*blobs):
    """util/maps.Merge: objects recurse, arrays concatenate, the later scalar wins."""
    def merge(a, b):
        out = dict(a)
        for k, vb in b.items():
            va = out.get(k)
            if isinstance(va, dict) and isinstance(vb, dict):
                out[k] = merge(va, vb)
            elif isinstance(va, list) and isinstance(vb, list):
                out[k] = va + vb
            elif vb is not None or va is None:
                out[k] = vb
        return out
    merged = {}
    for blob in blobs:
        merged = merge(merged, blob)
    return merged


def bundle(records, folded_cron=(), finished=True):
    """A policy bundle shaped like the hub's.

    `records` are the commit's own records, oldest first; `folded_cron` the
    default-branch cron records the merged blob folds in from other commits.
    """
    blobs = [CONTAINERS] + [{"container_scan": s} for s in folded_cron] + [
        r if "containers" in r else {"container_scan": r} for r in records]
    merged = hub_merge(*sorted(blobs, key=_observed))
    own = [CONTAINERS] + [r if "containers" in r else {"container_scan": r} for r in records]
    return Node.from_bundle_json({
        "merged_blob": merged,
        # The hub lists records newest first; get_all_values walks them in reverse.
        "metadata_instances": [{"payload": p} for p in reversed(own)],
        "bundle_info": {"workflows_finished": finished},
    })


def _observed(blob):
    return (blob.get("container_scan") or {}).get("source", {}).get("collected_at", "")


def run(module, n, **env):
    env.setdefault("LUNAR_VAR_min_severity", "high")
    with lunar_env(**env), contextlib.redirect_stdout(io.StringIO()):
        return module.main(node=n)


def release_gate(n):
    """The dogfood release gate's inputs."""
    return run(max_severity, n, LUNAR_VAR_ignore_unfixable="true")


class ReleaseShapeTests(unittest.TestCase):
    def test_merged_blob_alone_fails_on_the_folded_rescan(self):
        # Control arm: judging the merged blob is what failed the release.
        merged = bundle([FRESH_TRIVY, FRESH_GRYPE], folded_cron=[STALE_TRIVY_CRON, STALE_GRYPE_CRON])
        c = release_gate(Node.from_component_json(merged._data["merged_blob"],
                                                  bundle_info={"workflows_finished": True}))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn(f"high: golang.org/x/net — {X_NET} (fix: 0.62.0) [{HUB_OLD}, {SCRIPTS}]",
                      failure_message(c))

    def test_the_commits_own_scans_pass(self):
        c = release_gate(bundle([FRESH_TRIVY, FRESH_GRYPE],
                                folded_cron=[STALE_TRIVY_CRON, STALE_GRYPE_CRON]))
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_a_fixable_cve_in_the_commits_own_scan_still_fails(self):
        fresh = scan("trivy", "after-json", NEW, "2026-11-11T05:27:02Z", [HUB_NEW, SCRIPTS],
                     [finding("CVE-2026-1", HUB_NEW, package="openssl", fix="3.5.1")])
        c = release_gate(bundle([fresh, FRESH_GRYPE], folded_cron=[STALE_TRIVY_CRON]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn(f"high: openssl — CVE-2026-1 (fix: 3.5.1) [{HUB_NEW}]", msg)
        self.assertNotIn(X_NET, msg)


class SupersedeTests(unittest.TestCase):
    vulnerable = scan("trivy", "after-json", NEW, "2026-11-11T05:27:02Z", [HUB_NEW, SCRIPTS],
                      [finding(X_NET, HUB_NEW)])
    clean = scan("trivy", "cron", NEW, "2026-11-12T03:03:00Z", [HUB_NEW, SCRIPTS])

    def test_a_newer_scan_of_the_same_images_replaces_an_older_one(self):
        self.assertEqual(resolved_status(release_gate(bundle([self.vulnerable, self.clean]))),
                         CheckStatus.PASS)

    def test_a_newer_scan_with_a_new_cve_fails(self):
        newer = scan("trivy", "cron", NEW, "2026-11-12T03:03:00Z", [HUB_NEW, SCRIPTS],
                     [finding("CVE-2026-2", SCRIPTS, package="musl", fix="1.2.6")])
        older = scan("trivy", "after-json", NEW, "2026-11-11T05:27:02Z", [HUB_NEW, SCRIPTS])
        c = release_gate(bundle([older, newer]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn("CVE-2026-2", failure_message(c))

    def test_timestamps_decide_not_record_order(self):
        # Newest record first: the older vulnerable scan still loses.
        n = bundle([self.clean, self.vulnerable])
        self.assertEqual(resolved_status(release_gate(n)), CheckStatus.PASS)

    def test_scanners_are_judged_independently(self):
        grype_vulnerable = scan("grype", "after-json", NEW, "2026-11-11T05:28:00Z", [HUB_NEW, SCRIPTS],
                                [finding("GHSA-75pg-wvh3-34jr", HUB_NEW)])
        c = release_gate(bundle([grype_vulnerable, self.clean]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn("GHSA-75pg-wvh3-34jr", failure_message(c))

    def test_a_scan_with_errors_replaces_nothing(self):
        # Same images as the older scan, but it failed on one more: incomplete.
        errored = scan("trivy", "cron", NEW, "2026-11-12T03:03:00Z", [HUB_NEW, SCRIPTS],
                       errors=[{"image": f"earthly/lunar-dashboards:{NEW}", "error": "manifest unknown"}])
        c = release_gate(bundle([self.vulnerable, errored]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn(X_NET, failure_message(c))

    def test_a_scan_with_partial_counts_replaces_nothing(self):
        partial = scan("trivy", "cron", NEW, "2026-11-12T03:03:00Z", [HUB_NEW, SCRIPTS])
        partial["vulnerabilities"].pop("low")
        c = release_gate(bundle([self.vulnerable, partial]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn(X_NET, failure_message(c))

    def test_a_scan_of_fewer_images_replaces_nothing(self):
        older = scan("trivy", "after-json", NEW, "2026-11-11T05:27:02Z", [HUB_NEW, SCRIPTS],
                     [finding(X_NET, SCRIPTS)])
        newer = scan("trivy", "cron", NEW, "2026-11-12T03:03:00Z", [HUB_NEW])
        c = release_gate(bundle([older, newer]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn(f"[{SCRIPTS}]", failure_message(c))


class FallbackTests(unittest.TestCase):
    def test_no_scan_record_at_this_commit_uses_the_merged_data(self):
        # Nothing scanned here (no image built): judged on the folded rescan, as before.
        c = release_gate(bundle([], folded_cron=[STALE_TRIVY_CRON]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn(X_NET, failure_message(c))

    def test_pending_while_this_commits_scan_has_not_landed(self):
        c = release_gate(bundle([], folded_cron=[STALE_TRIVY_CRON], finished=False))
        self.assertEqual(c.status, CheckStatus.PENDING)

    def test_collectors_without_collected_at_use_the_merged_data(self):
        def legacy(s):
            return s | {"source": {k: v for k, v in s["source"].items() if k != "collected_at"}}
        c = release_gate(bundle([legacy(FRESH_TRIVY)], folded_cron=[legacy(STALE_TRIVY_CRON)]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)

    def test_counts_and_findings_written_separately_use_the_merged_data(self):
        counts = {k: v for k, v in FRESH_TRIVY.items() if k != "findings"}
        findings_only = {"findings": [finding(X_NET, HUB_NEW)]}
        c = release_gate(bundle([counts, findings_only]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn(X_NET, failure_message(c))

    def test_partial_writes_are_not_scans(self):
        # The run's raw-output record and a CI scanner's source fields carry no results.
        raw = {"native": {"trivy": {"results": {"SchemaVersion": 2}}}}
        ci_source = {"source": {"tool": "snyk", "integration": "ci"}}
        n = bundle([raw, ci_source, FRESH_TRIVY], folded_cron=[STALE_TRIVY_CRON])
        with lunar_env():
            self.assertEqual(scan_snapshots(n), [FRESH_TRIVY])


class PerScanVerdictTests(unittest.TestCase):
    def test_a_summary_only_scan_still_fails_beside_a_passing_one(self):
        summary_only = {k: v for k, v in scan("grype", "after-json", NEW, "2026-11-11T05:28:00Z",
                                              [HUB_NEW, SCRIPTS], [finding(X_NET, HUB_NEW)]).items()
                        if k != "findings"}
        c = release_gate(bundle([FRESH_TRIVY, summary_only]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn("fixability could not be verified", failure_message(c))

    def test_exemptions_apply_to_the_commits_own_findings(self):
        fresh = scan("trivy", "after-json", NEW, "2026-11-11T05:27:02Z", [HUB_NEW, SCRIPTS],
                     [finding("CVE-2026-1", HUB_NEW, package="openssl", fix="3.5.1")])
        c = run(max_severity, bundle([fresh], folded_cron=[STALE_TRIVY_CRON]),
                LUNAR_VAR_ignore_unfixable="true", LUNAR_VAR_exempt_findings="CVE-2026-1 openssl@v0.60.0")
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)


class UnfixableReviewedTests(unittest.TestCase):
    def test_lists_only_the_commits_own_unfixable_findings(self):
        stale = scan("trivy", "cron", OLD, "2026-11-11T03:03:38Z", [HUB_OLD],
                     [unfixable(HUB_OLD, cve="CVE-2026-9", package="zlib")])
        c = run(unfixable_reviewed, bundle([FRESH_TRIVY], folded_cron=[stale]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("CVE-2026-41567", msg)
        self.assertNotIn("CVE-2026-9", msg)

    def test_merged_blob_alone_also_lists_the_rescan(self):
        stale = scan("trivy", "cron", OLD, "2026-11-11T03:03:38Z", [HUB_OLD],
                     [unfixable(HUB_OLD, cve="CVE-2026-9", package="zlib")])
        merged = bundle([FRESH_TRIVY], folded_cron=[stale])._data["merged_blob"]
        c = run(unfixable_reviewed, Node.from_component_json(merged, bundle_info={"workflows_finished": True}))
        self.assertIn("CVE-2026-9", failure_message(c))


if __name__ == "__main__":
    unittest.main()
