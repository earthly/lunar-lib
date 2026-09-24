"""Unit tests for the k8s pdb check."""

import importlib.util
import unittest
from pathlib import Path

from lunar_policy import CheckStatus, Node

# pdb.py would shadow the stdlib debugger on a plain import; load it by path.
_spec = importlib.util.spec_from_file_location("k8s_pdb_policy", Path(__file__).parent / "pdb.py")
_pdb_policy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pdb_policy)
check_pdb, selector_matches = _pdb_policy.main, _pdb_policy.selector_matches


def deployment(name, labels, namespace="default", kind="Deployment", path="deploy/app.yaml"):
    return {"kind": kind, "name": name, "namespace": namespace, "path": path,
            "replicas": 2, "pod_labels": labels, "containers": []}


def pdb(selector, namespace="default", name="pdb"):
    # target_workload derived exactly as the collector derives it, so a fixture
    # means the same thing to the legacy name match as to selector matching.
    labels = (selector or {}).get("matchLabels") or {}
    return {"name": name, "namespace": namespace, "path": "deploy/pdb.yaml", "selector": selector,
            "target_workload": labels.get("app") or labels.get("app.kubernetes.io/name"),
            "min_available": 1}


def run(workloads, pdbs=None, finished=True):
    k8s = {"workloads": workloads}
    if pdbs is not None:
        k8s["pdbs"] = pdbs
    return check_pdb(Node.from_component_json({"k8s": k8s}, {"workflows_finished": finished}))


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


class SelectorMatchesTest(unittest.TestCase):
    def test_match_labels_is_an_and(self):
        self.assertTrue(selector_matches({"matchLabels": {"app": "a", "tier": "web"}},
                                         {"app": "a", "tier": "web", "extra": "x"}))
        self.assertFalse(selector_matches({"matchLabels": {"app": "a", "tier": "web"}}, {"app": "a"}))

    def test_in_and_not_in(self):
        sel = {"matchExpressions": [{"key": "tier", "operator": "In", "values": ["web", "api"]}]}
        self.assertTrue(selector_matches(sel, {"tier": "api"}))
        self.assertFalse(selector_matches(sel, {"tier": "db"}))
        self.assertFalse(selector_matches(sel, {}))
        sel = {"matchExpressions": [{"key": "tier", "operator": "NotIn", "values": ["db"]}]}
        self.assertTrue(selector_matches(sel, {"tier": "web"}))
        self.assertTrue(selector_matches(sel, {}), "NotIn matches when the key is absent")
        self.assertFalse(selector_matches(sel, {"tier": "db"}))

    def test_exists_and_does_not_exist(self):
        exists = {"matchExpressions": [{"key": "canary", "operator": "Exists"}]}
        absent = {"matchExpressions": [{"key": "canary", "operator": "DoesNotExist"}]}
        self.assertTrue(selector_matches(exists, {"canary": "true"}))
        self.assertFalse(selector_matches(exists, {}))
        self.assertTrue(selector_matches(absent, {}))
        self.assertFalse(selector_matches(absent, {"canary": "true"}))

    def test_labels_and_expressions_combine(self):
        sel = {"matchLabels": {"app": "a"},
               "matchExpressions": [{"key": "track", "operator": "NotIn", "values": ["canary"]}]}
        self.assertTrue(selector_matches(sel, {"app": "a", "track": "stable"}))
        self.assertFalse(selector_matches(sel, {"app": "a", "track": "canary"}))

    def test_empty_selects_all_null_selects_none(self):
        self.assertTrue(selector_matches({}, {"app": "anything"}))
        self.assertFalse(selector_matches(None, {"app": "anything"}))

    def test_unknown_operator_never_matches(self):
        self.assertFalse(selector_matches({"matchExpressions": [{"key": "a", "operator": "Gt", "values": ["1"]}]}, {"a": "2"}))

    def test_values_compare_as_strings(self):
        # YAML hands back unquoted numbers/bools as non-strings.
        self.assertTrue(selector_matches({"matchLabels": {"version": 2}}, {"version": "2"}))


class PdbCheckTest(unittest.TestCase):
    # The ticket's false FAILs: the workload has a PDB, the old name match missed it.
    def test_pdb_selecting_a_non_app_label_covers_the_workload(self):
        check = run([deployment("payments", {"app.kubernetes.io/instance": "payments-prod"})],
                    [pdb({"matchLabels": {"app.kubernetes.io/instance": "payments-prod"}})])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_match_expressions_only_pdb_covers_the_workload(self):
        check = run([deployment("payments", {"app": "payments", "tier": "api"})],
                    [pdb({"matchExpressions": [{"key": "tier", "operator": "In", "values": ["api"]}]})])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_app_label_differing_from_the_resource_name_covers_the_workload(self):
        check = run([deployment("payments-api-v2", {"app": "payments-api"})],
                    [pdb({"matchLabels": {"app": "payments-api"}})])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    # The ticket's false PASS: a name coincidence is not coverage.
    def test_name_coincidence_without_matching_labels_fails(self):
        check = run([deployment("foo", {"app": "bar"})],
                    [pdb({"matchLabels": {"app": "foo"}})])
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(failures(check), ["deploy/app.yaml: Deployment default/foo has no matching PodDisruptionBudget"])

    def test_pdb_in_another_namespace_does_not_count(self):
        check = run([deployment("payments", {"app": "payments"}, namespace="prod")],
                    [pdb({"matchLabels": {"app": "payments"}}, namespace="staging")])
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_empty_selector_covers_every_workload_in_its_namespace(self):
        check = run([deployment("a", {"app": "a"}), deployment("b", {"app": "b"}, kind="StatefulSet")],
                    [pdb({})])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_null_selector_covers_nothing(self):
        check = run([deployment("a", {"app": "a"})], [pdb(None)])
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_no_pdbs_fails_each_deployment_and_statefulset(self):
        check = run([deployment("a", {"app": "a"}), deployment("s", {"app": "s"}, kind="StatefulSet"),
                     deployment("d", {"app": "d"}, kind="DaemonSet")])
        self.assertEqual(len(failures(check)), 2, "DaemonSets are out of scope")

    def test_only_uncovered_workloads_are_reported(self):
        check = run([deployment("a", {"app": "a"}), deployment("b", {"app": "b"})],
                    [pdb({"matchLabels": {"app": "a"}})])
        self.assertEqual(failures(check), ["deploy/app.yaml: Deployment default/b has no matching PodDisruptionBudget"])

    # Component JSON from a collector that predates pod_labels / selector.
    def test_legacy_data_falls_back_to_the_target_name(self):
        legacy = {"kind": "Deployment", "name": "payment-api", "namespace": "payments", "path": "d.yaml"}
        covered = run([legacy], [{"name": "p", "namespace": "payments", "target_workload": "payment-api"}])
        self.assertEqual(covered.status, CheckStatus.PASS, failures(covered))
        missed = run([legacy], [{"name": "p", "namespace": "payments", "target_workload": "other"}])
        self.assertEqual(missed.status, CheckStatus.FAIL)

    def test_no_workloads_skips(self):
        check = check_pdb(Node.from_component_json({"k8s": {"manifests": []}}, {"workflows_finished": True}))
        self.assertTrue(any(r.result == CheckStatus.SKIPPED for r in check._results))

    def test_pending_while_collection_runs(self):
        check = check_pdb(Node.from_component_json({}, {"workflows_finished": False}))
        self.assertEqual(check.status, CheckStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
