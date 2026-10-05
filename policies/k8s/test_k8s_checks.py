"""Unit tests for the k8s checks' Helm render handling and the checks added with it."""

import copy
import importlib
import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

from lunar_policy import CheckStatus, Node

import helpers

HERE = Path(__file__).parent


def load(name):
    # pdb.py would shadow the stdlib debugger on a plain import; load every check by path.
    spec = importlib.util.spec_from_file_location(f"k8s_check_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


PROD = {"chart": "charts/api", "values": ["values.yaml", "values-prod.yaml"]}
STAGING = {"chart": "charts/api", "values": ["values.yaml", "values-staging.yaml"]}


def probe(port=8080, path="/healthz", period=10, timeout=1, handler="httpGet"):
    return {"handler": handler, "port": port, "path": path if handler == "httpGet" else None,
            "initial_delay_seconds": 0, "period_seconds": period, "timeout_seconds": timeout, "failure_threshold": 3}


def container(name="app", image="ghcr.io/acme/app:1.0", **overrides):
    c = {"name": name, "image": image, "has_resources": True, "has_requests": True, "has_limits": True,
         "cpu_request": "100m", "cpu_limit": "200m", "memory_request": "64Mi", "memory_limit": "128Mi",
         "has_liveness_probe": True, "has_readiness_probe": True,
         "liveness_probe": probe(path="/livez"), "readiness_probe": probe(path="/readyz"), "startup_probe": None,
         "has_prestop": True, "runs_as_non_root": True, "read_only_root_fs": True, "privileged": False}
    c.update(overrides)
    return c


def workload(name="api", kind="Deployment", namespace="default", path="deploy/api.yaml", render=None, **overrides):
    w = {"kind": kind, "name": name, "namespace": namespace, "path": path,
         "replicas": 3, "replicas_set": True, "pod_labels": {"app": name}, "pod_annotations": {},
         "host_users": False, "host_network": False, "host_pid": False, "host_ipc": False,
         "termination_grace_period_seconds": 60,
         "topology_spread_constraints": [{"topology_key": "topology.kubernetes.io/zone", "max_skew": 1,
                                          "when_unsatisfiable": "ScheduleAnyway",
                                          "label_selector": {"matchLabels": {"app": name}},
                                          "match_label_keys": ["pod-template-hash"]}],
         "containers": [container()], "init_containers": []}
    if render:
        w["render"] = render
        w["path"] = f"{render['chart']}/templates/deployment.yaml"
    w.update(overrides)
    return w


def pdb(name="api", namespace="default", render=None, selector=None, min_available=None, max_unavailable=1):
    p = {"name": name, "namespace": namespace, "path": "deploy/pdb.yaml",
         "selector": {"matchLabels": {"app": name}} if selector is None else selector,
         "target_workload": name, "min_available": min_available, "max_unavailable": max_unavailable}
    if render:
        p["render"] = render
        p["path"] = f"{render['chart']}/templates/pdb.yaml"
    return p


def hpa(name="api", target="api", min_replicas=2, max_replicas=6, render=None, kind="Deployment"):
    h = {"name": name, "namespace": "default", "path": "deploy/hpa.yaml", "target_workload": target,
         "target_kind": kind, "min_replicas": min_replicas, "max_replicas": max_replicas}
    if render:
        h["render"] = render
        h["path"] = f"{render['chart']}/templates/hpa.yaml"
    return h


def run(check, k8s, finished=True, **inputs):
    env = {f"LUNAR_VAR_{k}": v for k, v in inputs.items()}
    with mock.patch.dict(os.environ, env):
        return load(check)(Node.from_component_json({"k8s": k8s}, {"workflows_finished": finished}))


def failures(c):
    return [r.failure_message for r in c._results if r.result == CheckStatus.FAIL]


def skipped(c):
    return [r.failure_message for r in c._results if r.result == CheckStatus.SKIPPED]


def status(c):
    if skipped(c):
        return "skipped"
    return c.status.value if hasattr(c.status, "value") else str(c.status)


class HelperTest(unittest.TestCase):
    def test_values_label_drops_the_base_values_file(self):
        self.assertEqual(helpers.values_label({"render": PROD}), "values-prod.yaml")
        self.assertEqual(helpers.values_label({"render": {"chart": "c", "values": ["values.yaml"]}}), "values.yaml")
        self.assertEqual(helpers.values_label({"render": {"chart": "c", "values": ["values.yaml", "a.yaml", "b.yaml"]}}),
                         "a.yaml b.yaml")
        self.assertEqual(helpers.values_label({"path": "x"}), "")

    def test_same_release(self):
        plain = {"path": "deploy/pdb.yaml"}
        other = {"render": {"chart": "charts/other", "values": ["values.yaml"]}}
        self.assertTrue(helpers.same_release({"render": PROD}, plain))
        self.assertTrue(helpers.same_release({"render": PROD}, other))
        self.assertTrue(helpers.same_release({"render": PROD}, {"render": dict(PROD)}))
        self.assertFalse(helpers.same_release({"render": PROD}, {"render": STAGING}))

    def test_replica_range(self):
        w = workload(replicas=3)
        self.assertEqual(helpers.replica_range(w, []), (3, 3))
        self.assertEqual(helpers.replica_range(w, [("HorizontalPodAutoscaler", hpa(min_replicas=2, max_replicas=6))]), (2, 6))
        # KEDA's minReplicaCount defaults to 0: the smallest size still counts as one pod.
        self.assertEqual(helpers.replica_range(w, [("ScaledObject", {"min_replicas": 0, "max_replicas": 20})]), (1, 20))
        self.assertEqual(helpers.replica_range({"replicas": None}, []), (1, 1))

    def test_autoscalers_never_cross_values_sets_of_a_chart(self):
        w = workload(render=PROD)
        self.assertEqual(len(helpers.autoscalers_of(w, [hpa(render=PROD)], [])), 1)
        self.assertEqual(helpers.autoscalers_of(w, [hpa(render=STAGING)], []), [])
        self.assertEqual(len(helpers.autoscalers_of(w, [hpa()], [])), 1, "a plain-manifest HPA still matches")
        self.assertEqual(helpers.autoscalers_of(w, [hpa(kind="StatefulSet")], []), [], "scaleTargetRef.kind must match")


class RenderTest(unittest.TestCase):
    def test_a_finding_across_values_sets_is_reported_once(self):
        bare = container(has_requests=False, has_limits=False, cpu_request=None, cpu_limit=None,
                         memory_request=None, memory_limit=None)
        k8s = {"workloads": [workload(render=PROD, containers=[bare]), workload(render=STAGING, containers=[bare])]}
        self.assertEqual(failures(run("requests_and_limits", k8s)), [
            "charts/api/templates/deployment.yaml [values-prod.yaml, values-staging.yaml]: Deployment default/api container 'app' missing resource requests",
            "charts/api/templates/deployment.yaml [values-prod.yaml, values-staging.yaml]: Deployment default/api container 'app' missing resource limits",
        ])

    def test_only_the_failing_values_set_is_named(self):
        k8s = {"workloads": [workload(render=PROD), workload(render=STAGING, host_network=True)]}
        self.assertEqual(failures(run("host_network", k8s)), [
            "charts/api/templates/deployment.yaml [values-staging.yaml]: Deployment default/api should not set "
            "spec.hostNetwork: true (workload shares the host network namespace)"])

    def test_plain_manifest_messages_are_unchanged(self):
        k8s = {"workloads": [workload(containers=[container(runs_as_non_root=False)])]}
        self.assertEqual(failures(run("non_root", k8s)), [
            "deploy/api.yaml: Deployment default/api container 'app' should set securityContext.runAsNonRoot: true"])

    def test_valid_fails_a_chart_that_does_not_render(self):
        k8s = {"manifests": [
            {"path": "deploy/api.yaml", "valid": True, "resources": []},
            {"path": "charts/reports", "render": {"chart": "charts/reports", "values": ["values.yaml"], "validated_only": True},
             "valid": False, "resources": [], "error": "helm template: missing in charts/ directory: postgresql"},
        ]}
        self.assertEqual(failures(run("valid", k8s)),
                         ["charts/reports [values.yaml]: helm template: missing in charts/ directory: postgresql"])

    def test_workload_checks_point_at_helm_values_when_charts_are_build_only(self):
        k8s = {"manifests": [{"path": "charts/api", "render": {"chart": "charts/api", "values": ["values.yaml"],
                                                               "validated_only": True}, "valid": True, "resources": []}]}
        for check in ("probes", "requests_and_limits", "pdb", "topology_spread", "non_root"):
            self.assertEqual(skipped(run(check, k8s)), [helpers.NO_VALUES_SET], check)
        self.assertEqual(status(run("valid", k8s)), "pass")

    def test_no_workloads_without_charts_keeps_the_old_reason(self):
        k8s = {"manifests": [{"path": "deploy/cm.yaml", "valid": True, "resources": []}]}
        self.assertEqual(skipped(run("probes", k8s)), ["No Kubernetes workloads found in this repository"])

    def test_pending_while_collection_runs(self):
        self.assertEqual(run("probes", {}, finished=False).status, CheckStatus.PENDING)
        self.assertEqual(run("topology_spread", {}, finished=False).status, CheckStatus.PENDING)

    def test_pdb_from_another_values_set_does_not_cover(self):
        k8s = {"workloads": [workload(render=PROD)], "pdbs": [pdb(render=STAGING)]}
        self.assertEqual(failures(run("pdb", k8s)), [
            "charts/api/templates/deployment.yaml [values-prod.yaml]: Deployment default/api has no matching PodDisruptionBudget"])
        k8s["pdbs"].append(pdb(render=PROD))
        self.assertEqual(failures(run("pdb", k8s)), [])

    def test_plain_manifest_pdb_covers_a_chart_workload(self):
        self.assertEqual(failures(run("pdb", {"workloads": [workload(render=PROD)], "pdbs": [pdb()]})), [])

    def test_network_policy_from_another_values_set_does_not_select(self):
        netpol = {"name": "deny", "namespace": "default", "path": "charts/api/templates/netpol.yaml", "render": STAGING,
                  "pod_selector": {}, "policy_types": ["Egress"], "egress": []}
        k8s = {"workloads": [workload(render=PROD)], "network_policies": [netpol]}
        self.assertEqual(len(failures(run("metadata_egress_blocked", k8s))), 1)
        netpol["render"] = PROD
        self.assertEqual(failures(run("metadata_egress_blocked", k8s)), [])


class TopologySpreadTest(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(failures(run("topology_spread", {"workloads": [workload()]})), [])

    def test_missing_constraint(self):
        k8s = {"workloads": [workload(render=PROD, topology_spread_constraints=[])]}
        self.assertEqual(failures(run("topology_spread", k8s)), [
            "charts/api/templates/deployment.yaml [values-prod.yaml]: Deployment default/api has no "
            "topologySpreadConstraint on topology.kubernetes.io/zone"])

    def test_single_replica_is_exempt_unless_an_autoscaler_grows_it(self):
        w = workload(replicas=1, topology_spread_constraints=[])
        self.assertEqual(skipped(run("topology_spread", {"workloads": [w]})),
                         ["No Deployment or StatefulSet in this repository can run more than one replica"])
        self.assertEqual(len(failures(run("topology_spread", {"workloads": [w], "hpas": [hpa(min_replicas=1, max_replicas=4)]}))), 1)

    def test_constraint_must_select_the_pods_and_respect_skew(self):
        w = workload()
        w["topology_spread_constraints"][0]["label_selector"] = {"matchLabels": {"app": "other"}}
        w["topology_spread_constraints"][0]["max_skew"] = 2
        self.assertEqual(failures(run("topology_spread", {"workloads": [w]})), [
            "deploy/api.yaml: Deployment default/api topologySpreadConstraint on topology.kubernetes.io/zone: its "
            "labelSelector doesn't select the workload's pods; maxSkew 2 is above 1"])
        self.assertEqual(failures(run("topology_spread", {"workloads": [workload()]}, topology_max_skew="1")), [])

    def test_optional_requirements(self):
        w = workload()
        w["topology_spread_constraints"][0]["match_label_keys"] = []
        self.assertEqual(failures(run("topology_spread", {"workloads": [w]})), [])
        self.assertEqual(len(failures(run("topology_spread", {"workloads": [w]}, topology_require_match_label_keys="true"))), 1)
        self.assertEqual(len(failures(run("topology_spread", {"workloads": [w]}, topology_when_unsatisfiable="DoNotSchedule"))), 1)
        self.assertEqual(failures(run("topology_spread", {"workloads": [w]}, topology_key="kubernetes.io/hostname")), [
            "deploy/api.yaml: Deployment default/api has no topologySpreadConstraint on kubernetes.io/hostname"])

    def test_skips_an_older_collector(self):
        w = workload()
        del w["topology_spread_constraints"]
        self.assertTrue(skipped(run("topology_spread", {"workloads": [w]}))[0].startswith("The k8s collector predates"))

    def test_skips_without_deployments(self):
        self.assertEqual(skipped(run("topology_spread", {"workloads": [workload(kind="DaemonSet")]})),
                         ["No Deployments or StatefulSets found in this repository"])


class GracefulShutdownTest(unittest.TestCase):
    def test_pass_and_fail(self):
        self.assertEqual(failures(run("graceful_shutdown", {"workloads": [workload()]})), [])
        w = workload(termination_grace_period_seconds=10, containers=[container(has_prestop=False)])
        self.assertEqual(failures(run("graceful_shutdown", {"workloads": [w]})), [
            "deploy/api.yaml: Deployment default/api has no container with a preStop hook",
            "deploy/api.yaml: Deployment default/api has terminationGracePeriodSeconds 10, below 30"])

    def test_inputs(self):
        w = workload(termination_grace_period_seconds=30, containers=[container(has_prestop=False)])
        self.assertEqual(failures(run("graceful_shutdown", {"workloads": [w]}, require_prestop="false")), [])
        self.assertEqual(failures(run("graceful_shutdown", {"workloads": [w]}, require_prestop="false",
                                      min_termination_grace_period_seconds="60")),
                         ["deploy/api.yaml: Deployment default/api has terminationGracePeriodSeconds 30, below 60"])


class PdbBudgetTest(unittest.TestCase):
    def test_max_unavailable(self):
        self.assertEqual(failures(run("pdb_budget", {"workloads": [workload()], "pdbs": [pdb(max_unavailable=1)]})), [])
        for zero in (0, "0%"):
            self.assertEqual(failures(run("pdb_budget", {"workloads": [workload()], "pdbs": [pdb(max_unavailable=zero)]})),
                             [f"deploy/pdb.yaml: PodDisruptionBudget default/api allows no voluntary disruptions: maxUnavailable is {zero}"])

    def test_min_available_against_the_smallest_size(self):
        k8s = {"workloads": [workload(render=PROD)], "pdbs": [pdb(render=PROD, min_available=2, max_unavailable=None)],
               "hpas": [hpa(render=PROD, min_replicas=2, max_replicas=6)]}
        self.assertEqual(failures(run("pdb_budget", k8s)), [
            "charts/api/templates/pdb.yaml [values-prod.yaml]: PodDisruptionBudget default/api allows no voluntary "
            "disruptions: minAvailable 2 covers Deployment api, which runs at least 2 replicas"])
        k8s["hpas"][0]["min_replicas"] = 3
        self.assertEqual(failures(run("pdb_budget", k8s)), [])

    def test_percentages_round_up(self):
        def budget(value):
            return failures(run("pdb_budget", {"workloads": [workload(replicas=3)],
                                               "pdbs": [pdb(min_available=value, max_unavailable=None)]}))
        self.assertEqual(budget("50%"), [])
        self.assertEqual(len(budget("67%")), 1)
        self.assertEqual(len(budget("100%")), 1)

    def test_structure(self):
        k8s = {"workloads": [workload()], "pdbs": [pdb(selector={}, min_available=1, max_unavailable=1)]}
        self.assertEqual(failures(run("pdb_budget", k8s)),
                         ["deploy/pdb.yaml: PodDisruptionBudget default/api sets both minAvailable and maxUnavailable; set one"])
        no_selector = pdb(max_unavailable=1)
        no_selector["selector"] = None
        self.assertEqual(failures(run("pdb_budget", {"workloads": [workload()], "pdbs": [no_selector]})),
                         ["deploy/pdb.yaml: PodDisruptionBudget default/api has no selector, so it covers no pods"])

    def test_a_budget_over_several_workloads_counts_their_pods_together(self):
        k8s = {"workloads": [workload("a", replicas=2, pod_labels={"tier": "web"}),
                             workload("b", replicas=2, pod_labels={"tier": "web"})],
               "pdbs": [pdb("web", selector={"matchLabels": {"tier": "web"}}, min_available=3, max_unavailable=None)]}
        self.assertEqual(failures(run("pdb_budget", k8s)), [])
        k8s["pdbs"][0]["min_available"] = 4
        self.assertEqual(failures(run("pdb_budget", k8s)), [
            "deploy/pdb.yaml: PodDisruptionBudget default/web allows no voluntary disruptions: minAvailable 4 covers "
            "Deployment a and Deployment b, which run at least 4 replicas together"])

    def test_skips_without_pdbs(self):
        self.assertEqual(skipped(run("pdb_budget", {"workloads": [workload()]})),
                         ["No PodDisruptionBudgets found in this repository"])


class NoStaticReplicasTest(unittest.TestCase):
    def test_fails_replicas_on_an_autoscaled_workload(self):
        k8s = {"workloads": [workload(replicas=2)], "hpas": [hpa()], "scaled_objects": []}
        self.assertEqual(failures(run("no_static_replicas", k8s)), [
            "deploy/api.yaml: Deployment default/api sets spec.replicas: 2 while HorizontalPodAutoscaler api scales it"])
        k8s["workloads"][0]["replicas_set"] = False
        self.assertEqual(failures(run("no_static_replicas", k8s)), [])

    def test_scaled_object_and_values_sets(self):
        so = {"name": "api", "namespace": "default", "path": "charts/api/templates/so.yaml", "render": STAGING,
              "target_workload": "api", "target_kind": "Deployment", "min_replicas": 0, "max_replicas": 20}
        k8s = {"workloads": [workload(render=PROD)], "hpas": [], "scaled_objects": [so]}
        self.assertEqual(failures(run("no_static_replicas", k8s)), [])
        so["render"] = PROD
        self.assertEqual(len(failures(run("no_static_replicas", k8s))), 1)

    def test_skips_without_autoscalers(self):
        self.assertEqual(skipped(run("no_static_replicas", {"workloads": [workload()], "hpas": [], "scaled_objects": []})),
                         ["No HorizontalPodAutoscalers or ScaledObjects found in this repository"])


class ProbeTests(unittest.TestCase):
    def test_probes_distinct(self):
        self.assertEqual(failures(run("probes_distinct", {"workloads": [workload()]})), [])
        same = container(liveness_probe=probe(path="/healthz"), readiness_probe=probe(path="/healthz", timeout=2))
        self.assertEqual(failures(run("probes_distinct", {"workloads": [workload(containers=[same])]})), [
            "deploy/api.yaml: Deployment default/api container 'app' livenessProbe and readinessProbe both check httpGet :8080/healthz"])
        tcp = container(liveness_probe=probe(handler="tcpSocket"), readiness_probe=probe(handler="tcpSocket"))
        self.assertEqual(len(failures(run("probes_distinct", {"workloads": [workload(containers=[tcp])]}))), 1)

    def test_probe_timeouts(self):
        slow = container(liveness_probe=probe(timeout=10, period=10))
        self.assertEqual(failures(run("probe_timeouts", {"workloads": [workload(containers=[slow])]})), [
            "deploy/api.yaml: Deployment default/api container 'app' livenessProbe timeoutSeconds 10 is not below periodSeconds 10"])
        self.assertEqual(len(failures(run("probe_timeouts", {"workloads": [workload()]}, min_probe_timeout_seconds="2"))), 2)
        self.assertEqual(failures(run("probe_timeouts", {"workloads": [workload()]})), [])

    def test_skip_an_older_collector(self):
        old = container()
        del old["liveness_probe"]
        for check in ("probes_distinct", "probe_timeouts"):
            self.assertTrue(skipped(run(check, {"workloads": [workload(containers=[old])]}))[0].startswith(
                "The k8s collector predates"), check)


class OptInTests(unittest.TestCase):
    def test_allowed_registries(self):
        k8s = {"workloads": [workload(containers=[container(image="nginx:1.25")],
                                      init_containers=[container("init", image="ghcr.io/acme/migrate:1")])]}
        self.assertEqual(skipped(run("allowed_registries", k8s)), ["allowed_registries is not set"])
        self.assertEqual(failures(run("allowed_registries", k8s, allowed_registries="ghcr.io/acme")), [
            "deploy/api.yaml: Deployment default/api container 'app' image nginx:1.25 (docker.io/library/nginx) "
            "is not from an allowed registry"])
        self.assertEqual(failures(run("allowed_registries", k8s, allowed_registries="ghcr.io/acme, docker.io/library")), [])
        self.assertEqual(len(failures(run("allowed_registries", k8s, allowed_registries="ghcr.io/acm"))), 2,
                         "an entry matches whole path components")

    def test_deprecated_api_versions(self):
        k8s = {"manifests": [{"path": "charts/api", "render": dict(PROD, validated_only=False), "valid": True,
                              "resources": [{"kind": "PodDisruptionBudget", "name": "api", "namespace": "default",
                                             "api_version": "policy/v1beta1"},
                                            {"kind": "Ingress", "name": "api", "namespace": "default",
                                             "api_version": "networking.k8s.io/v1"}]}]}
        self.assertEqual(skipped(run("deprecated_api_versions", k8s)), ["deprecated_api_versions is not set"])
        self.assertEqual(failures(run("deprecated_api_versions", k8s, deprecated_api_versions="policy/v1beta1")), [
            "charts/api [values-prod.yaml]: PodDisruptionBudget default/api uses deprecated apiVersion policy/v1beta1"])
        self.assertEqual(failures(run("deprecated_api_versions", k8s,
                                      deprecated_api_versions="networking.k8s.io/v1:Service")), [])
        old = copy.deepcopy(k8s)
        del old["manifests"][0]["resources"][0]["api_version"]
        self.assertTrue(skipped(run("deprecated_api_versions", old, deprecated_api_versions="policy/v1beta1"))[0]
                        .startswith("The k8s collector predates"))

    def test_pod_annotations(self):
        w = workload(pod_annotations={"karpenter.sh/do-not-disrupt": "true"})
        self.assertEqual(skipped(run("pod_annotations", {"workloads": [w]})),
                         ["Neither required_pod_annotations nor forbidden_pod_annotations is set"])
        self.assertEqual(failures(run("pod_annotations", {"workloads": [w]},
                                      forbidden_pod_annotations="karpenter.sh/do-not-disrupt",
                                      required_pod_annotations="prometheus.io/scrape")), [
            "deploy/api.yaml: Deployment default/api pod template is missing required annotation prometheus.io/scrape",
            "deploy/api.yaml: Deployment default/api pod template sets forbidden annotation karpenter.sh/do-not-disrupt"])
        patch = workload(pod_labels={}, pod_annotations={})
        self.assertEqual(skipped(run("pod_annotations", {"workloads": [patch]}, required_pod_annotations="a/b")),
                         ["Only partial manifests here, such as kustomize patches, which leave required annotations "
                          "to the definition they patch"])

    def test_checks_that_checked_nothing_skip(self):
        no_probes = container(has_liveness_probe=False, has_readiness_probe=False, liveness_probe=None, readiness_probe=None)
        k8s = {"workloads": [workload(containers=[no_probes])]}
        self.assertEqual(skipped(run("probes_distinct", k8s)), ["No container has both a liveness and a readiness probe"])
        self.assertEqual(skipped(run("probe_timeouts", k8s)), ["No probes found in this repository"])
        k8s = {"workloads": [workload(name="other")], "hpas": [hpa()], "scaled_objects": []}
        self.assertEqual(skipped(run("no_static_replicas", k8s)),
                         ["No HorizontalPodAutoscaler or ScaledObject scales a Deployment or StatefulSet in this repository"])


if __name__ == "__main__":
    unittest.main()
