"""Unit tests for the k8s metadata-egress-blocked check.

Fixtures use the shape the k8s collector writes to .k8s.network_policies:
pod_selector and egress verbatim from the manifest, policy_types defaulted the
way the API server defaults it (collectors/k8s/test pins that side).
"""

import os
import unittest
from unittest import mock

from lunar_policy import CheckStatus, Node

from metadata_egress_blocked import main as check_metadata_egress

IMDS_BLOCKED = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["169.254.169.254/32"]}}]}]


def workload(name, labels, namespace="default", kind="Deployment", path="deploy/app.yaml", **extra):
    return {"kind": kind, "name": name, "namespace": namespace, "path": path,
            "replicas": 1, "pod_labels": labels, "containers": [], **extra}


def netpol(name="np", egress=None, pod_selector=None, namespace="default", policy_types=("Egress",)):
    return {"name": name, "namespace": namespace, "path": "deploy/netpol.yaml",
            "pod_selector": {} if pod_selector is None else pod_selector,
            "policy_types": list(policy_types), "egress": egress or []}


def run(workloads, policies=None, finished=True, metadata_ips=None):
    k8s = {"workloads": workloads}
    if policies is not None:
        k8s["network_policies"] = policies
    env = {} if metadata_ips is None else {"LUNAR_VAR_metadata_ips": metadata_ips}
    with mock.patch.dict(os.environ, env):
        return check_metadata_egress(Node.from_component_json({"k8s": k8s}, {"workflows_finished": finished}))


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def skipped(check):
    return any(r.result == CheckStatus.SKIPPED for r in check._results)


class CoveredTest(unittest.TestCase):
    def test_namespace_wide_allow_all_except_metadata_passes(self):
        check = run([workload("api", {"app": "api"})], [netpol(egress=IMDS_BLOCKED)])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_default_deny_egress_passes(self):
        # No egress rules with Egress in policyTypes: the pod may send nothing.
        check = run([workload("api", {"app": "api"})], [netpol(egress=[])])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_per_workload_selector_passes(self):
        check = run([workload("api", {"app": "api"})],
                    [netpol(egress=IMDS_BLOCKED, pod_selector={"matchLabels": {"app": "api"}})])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_rules_to_pods_and_namespaces_never_reach_the_metadata_ip(self):
        egress = [{"to": [{"namespaceSelector": {}},
                          {"podSelector": {"matchLabels": {"app": "db"}}},
                          {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
                           "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}}}]}]
        self.assertEqual(run([workload("api", {})], [netpol(egress=egress)]).status, CheckStatus.PASS)

    def test_ip_block_elsewhere_passes(self):
        egress = [{"to": [{"ipBlock": {"cidr": "10.0.0.0/8"}}, {"ipBlock": {"cidr": "2001:db8::/32"}}]}]
        self.assertEqual(run([workload("api", {})], [netpol(egress=egress)]).status, CheckStatus.PASS)

    def test_a_wider_except_also_covers_it(self):
        egress = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["169.254.0.0/16"]}}]}]
        self.assertEqual(run([workload("api", {})], [netpol(egress=egress)]).status, CheckStatus.PASS)

    def test_rules_limited_to_other_ports_pass(self):
        egress = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}], "ports": [{"protocol": "TCP", "port": 443}]},
                  {"ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 8000, "endPort": 9000}]}]
        check = run([workload("api", {})], [netpol(egress=egress)])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_port_80_on_another_protocol_passes(self):
        # The metadata service is TCP; UDP or SCTP port 80 doesn't reach it.
        for protocol in ("UDP", "SCTP"):
            egress = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}], "ports": [{"protocol": protocol, "port": 80}]}]
            check = run([workload("api", {})], [netpol(egress=egress)])
            self.assertEqual(check.status, CheckStatus.PASS, (protocol, failures(check)))

    def test_named_port_cannot_match_the_metadata_ip(self):
        # A named port resolves against the destination pod's ports.
        egress = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}], "ports": [{"port": "http"}]}]
        self.assertEqual(run([workload("api", {})], [netpol(egress=egress)]).status, CheckStatus.PASS)


class OpenTest(unittest.TestCase):
    def test_no_network_policies_fails_each_workload(self):
        check = run([workload("api", {"app": "api"}), workload("worker", {"app": "w"}, kind="CronJob")])
        self.assertEqual(failures(check), [
            "deploy/app.yaml: Deployment default/api can reach 169.254.169.254: no NetworkPolicy selects it for egress",
            "deploy/app.yaml: CronJob default/worker can reach 169.254.169.254: no NetworkPolicy selects it for egress",
        ])

    def test_ingress_only_policy_does_not_restrict_egress(self):
        # policyTypes defaulted to [Ingress] because the manifest had no egress rules.
        check = run([workload("api", {})], [netpol(policy_types=("Ingress",))])
        self.assertEqual(len(failures(check)), 1)
        self.assertIn("no NetworkPolicy selects it for egress", failures(check)[0])

    def test_policy_selecting_other_pods_does_not_count(self):
        check = run([workload("api", {"app": "api"})],
                    [netpol(egress=IMDS_BLOCKED, pod_selector={"matchLabels": {"app": "web"}})])
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_policy_in_another_namespace_does_not_count(self):
        check = run([workload("api", {}, namespace="payments")], [netpol(egress=IMDS_BLOCKED, namespace="staging")])
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_rule_with_no_to_allows_everything(self):
        check = run([workload("api", {})], [netpol(name="allow-all", egress=[{}])])
        self.assertEqual(failures(check), [
            "deploy/app.yaml: Deployment default/api can reach 169.254.169.254: NetworkPolicy default/allow-all "
            "has an egress rule with no `to`, which allows every destination"])

    def test_ip_block_without_except_fails(self):
        egress = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}]
        check = run([workload("api", {})], [netpol(name="egress", egress=egress)])
        self.assertEqual(failures(check), [
            "deploy/app.yaml: Deployment default/api can reach 169.254.169.254: NetworkPolicy default/egress "
            "allows ipBlock 0.0.0.0/0 without excepting it"])

    def test_explicit_allow_of_the_endpoint_fails(self):
        # e.g. GKE Workload Identity setups allow it on purpose; the check still reports it.
        egress = [{"to": [{"ipBlock": {"cidr": "169.254.169.254/32"}}], "ports": [{"protocol": "TCP", "port": 80}]}]
        check = run([workload("api", {})], [netpol(name="allow-metadata", egress=egress)])
        self.assertEqual(failures(check), [
            "deploy/app.yaml: Deployment default/api can reach 169.254.169.254: NetworkPolicy default/allow-metadata "
            "allows ipBlock 169.254.169.254/32"])

    def test_except_for_a_different_address_does_not_help(self):
        egress = [{"to": [{"ipBlock": {"cidr": "169.254.0.0/16", "except": ["169.254.170.23/32"]}}]}]
        self.assertEqual(run([workload("api", {})], [netpol(egress=egress)]).status, CheckStatus.FAIL)

    def test_policies_are_additive(self):
        # One policy blocks the endpoint, another selecting the same pods reopens it.
        check = run([workload("api", {"app": "api"})],
                    [netpol("block", egress=IMDS_BLOCKED),
                     netpol("reopen", egress=[{}], pod_selector={"matchLabels": {"app": "api"}})])
        self.assertEqual(len(failures(check)), 1)
        self.assertIn("NetworkPolicy default/reopen", failures(check)[0])

    def test_port_80_or_a_range_containing_it_reaches_it(self):
        for ports in ([{"port": 80}], [{"protocol": "TCP", "port": 1, "endPort": 1024}], [{"protocol": "TCP"}], [{"port": "80"}]):
            egress = [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}], "ports": ports}]
            self.assertEqual(run([workload("api", {})], [netpol(egress=egress)]).status, CheckStatus.FAIL, ports)

    def test_unparseable_cidr_is_not_trusted(self):
        egress = [{"to": [{"ipBlock": {"cidr": "not-a-cidr"}}]}]
        self.assertEqual(run([workload("api", {})], [netpol(egress=egress)]).status, CheckStatus.FAIL)

    def test_only_open_workloads_are_reported(self):
        check = run([workload("api", {"app": "api"}), workload("web", {"app": "web"})],
                    [netpol(egress=IMDS_BLOCKED, pod_selector={"matchLabels": {"app": "api"}})])
        self.assertEqual(len(failures(check)), 1)
        self.assertIn("Deployment default/web", failures(check)[0])


class MetadataIpsInputTest(unittest.TestCase):
    def test_ipv6_endpoint_is_checked_when_configured(self):
        egress = IMDS_BLOCKED + [{"to": [{"ipBlock": {"cidr": "::/0"}}]}]
        self.assertEqual(run([workload("api", {})], [netpol(egress=egress)]).status, CheckStatus.PASS)
        check = run([workload("api", {})], [netpol(egress=egress)], metadata_ips="169.254.169.254, fd00:ec2::254")
        self.assertEqual(len(failures(check)), 1)
        self.assertIn("can reach fd00:ec2::254", failures(check)[0])

    def test_invalid_entry_is_a_misconfiguration(self):
        with self.assertRaises(ValueError) as ctx:
            run([workload("api", {})], [netpol(egress=IMDS_BLOCKED)], metadata_ips="169.254.169.254,metadata")
        self.assertIn("misconfiguration", str(ctx.exception))


class ScopeTest(unittest.TestCase):
    def test_patch_is_selected_through_the_definition_it_patches(self):
        base = workload("api", {"app": "api"}, path="base/deploy.yaml")
        patch = workload("api", {}, path="overlays/prod/patch.yaml")
        selector = {"matchLabels": {"app": "api"}}
        self.assertEqual(run([base, patch], [netpol(egress=IMDS_BLOCKED, pod_selector=selector)]).status,
                         CheckStatus.PASS)

    def test_host_network_workloads_are_left_to_host_network(self):
        check = run([workload("cni", {}, kind="DaemonSet", host_network=True), workload("api", {})],
                    [netpol(egress=IMDS_BLOCKED, pod_selector={"matchLabels": {"app": "nothing"}})])
        self.assertEqual(len(failures(check)), 1)
        self.assertIn("Deployment default/api", failures(check)[0])

    def test_only_host_network_workloads_skips(self):
        check = run([workload("cni", {}, kind="DaemonSet", host_network=True)])
        self.assertTrue(skipped(check))
        self.assertEqual(failures(check), [])

    def test_no_workloads_skips(self):
        self.assertTrue(skipped(run([])))
        self.assertTrue(skipped(check_metadata_egress(
            Node.from_component_json({"k8s": {"manifests": []}}, {"workflows_finished": True}))))

    def test_pending_while_collection_runs(self):
        check = check_metadata_egress(Node.from_component_json({}, {"workflows_finished": False}))
        self.assertEqual(check.status, CheckStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
