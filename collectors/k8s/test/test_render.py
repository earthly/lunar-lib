"""Helm rendering and workload field tests for the k8s collector.

These build charts in a scratch repo and run the real render.sh with the
image's helm, yq and jq (and main.sh for static manifests). Only `lunar` (to
capture what is collected) and `kubeconform` (it fetches schemas over the
network) are stubbed.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_SH = os.path.join(HERE, "..", "render.sh")
MAIN_SH = os.path.join(HERE, "..", "main.sh")

DEPLOYMENT = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}
spec:
  {{- if not .Values.autoscaling }}
  replicas: {{ .Values.replicas }}
  {{- end }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
    spec:
      containers:
        - name: app
          image: {{ .Values.image }}
          resources: {{- toYaml .Values.resources | nindent 12 }}
"""

HPA = """\
{{- if .Values.autoscaling }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ .Release.Name }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ .Release.Name }}
  minReplicas: 2
  maxReplicas: 6
{{- end }}
"""

SCALED_OBJECT = """\
{{- if .Capabilities.APIVersions.Has "keda.sh/v1alpha1" }}
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: {{ .Release.Name }}
spec:
  scaleTargetRef:
    name: {{ .Release.Name }}
  minReplicaCount: 2
  maxReplicaCount: 20
  triggers:
    - type: cpu
      metadata:
        value: "50"
{{- end }}
"""

VALUES = "image: ghcr.io/acme/app:1.0\nreplicas: 1\nautoscaling: false\nresources: {}\n"


class Harness(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.bin = tempfile.mkdtemp()
        self.capture = os.path.join(self.bin, "captured.jsonl")
        self.kubeconform_fails = os.path.join(self.bin, "kubeconform-fails")
        stubs = {
            "lunar": f"""\
                #!/bin/bash
                [ "$1" = "collect" ] || exit 0
                shift; [ "$1" = "-j" ] && shift
                jq -c --arg path "$1" '{{path: $path, value: .}}' >> {self.capture}
                """,
            # Fails, naming the first file it was given, once the test creates the marker.
            "kubeconform": f"""\
                #!/bin/bash
                [ "$1" = "-v" ] && echo "v0.8.0" && exit 0
                if [ -f {self.kubeconform_fails} ]; then
                    target="${{@: -1}}"
                    file=$(find "$target" -type f | sort | head -1)
                    echo "$file - Deployment app is invalid: problem validating schema"
                    exit 1
                fi
                exit 0
                """,
        }
        for name, body in stubs.items():
            path = os.path.join(self.bin, name)
            with open(path, "w") as fh:
                fh.write(textwrap.dedent(body))
            os.chmod(path, 0o755)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.bin, ignore_errors=True)

    def write(self, rel, body):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(body)

    def chart(self, rel, name=None, values=VALUES, templates=None, extra="", overlays=None):
        name = name or os.path.basename(rel)
        self.write(f"{rel}/Chart.yaml", f"apiVersion: v2\nname: {name}\nversion: 0.1.0\n{extra}")
        if values is not None:
            self.write(f"{rel}/values.yaml", values)
        for tname, body in (templates if templates is not None else {"deployment.yaml": DEPLOYMENT}).items():
            self.write(f"{rel}/templates/{tname}", body)
        for oname, body in (overlays or {}).items():
            self.write(f"{rel}/{oname}", body)

    def run_script(self, script, **inputs):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"])
        env.update({f"LUNAR_VAR_{k.upper()}": v for k, v in inputs.items()})
        return subprocess.run(["bash", script], cwd=self.repo, env=env, capture_output=True, text=True)

    def collect(self, script=RENDER_SH, **inputs):
        proc = self.run_script(script, **inputs)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not os.path.exists(self.capture):
            return {}
        with open(self.capture) as fh:
            return {rec["path"]: rec["value"] for rec in map(json.loads, fh)}

    def renders(self, **inputs):
        k8s = self.collect(**inputs).get(".k8s", {})
        return k8s, [(m["path"], m["render"]["values"], m["render"]["validated_only"], m["valid"])
                     for m in k8s.get("manifests", [])]


class RenderTest(Harness):
    def test_no_charts_writes_nothing(self):
        self.write("deploy/app.yaml", "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\n")
        self.assertEqual(self.collect(), {})

    def test_a_chart_no_values_set_applies_to_is_only_checked_to_build(self):
        self.chart("charts/api")
        k8s, renders = self.renders()
        self.assertEqual(renders, [("charts/api", ["values.yaml"], True, True)])
        self.assertEqual(k8s["manifests"][0]["resources"], [])
        self.assertEqual(k8s["workloads"], [])

    def test_chains_from_overlay_names(self):
        self.chart("charts/api", overlays={
            "values-prod.yaml": "replicas: 3\n",
            "values-prod-eu.yaml": "replicas: 4\n",
            "values-staging.yaml": "replicas: 2\n",
        })
        k8s, renders = self.renders(helm_values_chains="overlays")
        self.assertEqual(renders, [
            ("charts/api", ["values.yaml", "values-prod.yaml", "values-prod-eu.yaml"], False, True),
            ("charts/api", ["values.yaml", "values-staging.yaml"], False, True),
        ])
        self.assertEqual([(w["path"], w["render"], w["replicas"], w["replicas_set"]) for w in k8s["workloads"]], [
            ("charts/api/templates/deployment.yaml",
             {"chart": "charts/api", "values": ["values.yaml", "values-prod.yaml", "values-prod-eu.yaml"]}, 4, True),
            ("charts/api/templates/deployment.yaml",
             {"chart": "charts/api", "values": ["values.yaml", "values-staging.yaml"]}, 2, True),
        ])
        self.assertEqual(k8s["manifests"][0]["resources"],
                         [{"kind": "Deployment", "name": "api", "namespace": "default", "api_version": "apps/v1"}])

    def test_an_overlay_extends_another_only_at_a_dash(self):
        self.chart("charts/api", overlays={"values-pro.yaml": "replicas: 2\n", "values-prod.yaml": "replicas: 3\n"})
        _, renders = self.renders(helm_values_chains="overlays")
        self.assertEqual([r[1] for r in renders], [["values.yaml", "values-pro.yaml"], ["values.yaml", "values-prod.yaml"]])

    def test_chains_overlays_leaves_a_chart_without_overlays_build_only_and_all_checks_it(self):
        self.chart("charts/lib-defaults")
        _, renders = self.renders(helm_values_chains="overlays")
        self.assertEqual(renders, [("charts/lib-defaults", ["values.yaml"], True, True)])
        os.remove(self.capture)
        k8s, renders = self.renders(helm_values_chains="all")
        self.assertEqual(renders, [("charts/lib-defaults", ["values.yaml"], False, True)])
        self.assertEqual(len(k8s["workloads"]), 1)

    def test_helm_values_lines_globs_and_missing_files(self):
        self.chart("charts/api", overlays={
            "values-prod.yaml": "autoscaling: true\n",
            "ci/a-values.yaml": "replicas: 2\n",
            "ci/b-values.yaml": "replicas: 3\n",
        })
        k8s, renders = self.renders(helm_values="values.yaml\nvalues-prod.yaml  # prod\nci/*-values.yaml\nmissing.yaml\n")
        self.assertEqual([r[1] for r in renders], [
            ["values.yaml"], ["values.yaml", "values-prod.yaml"],
            ["values.yaml", "ci/a-values.yaml"], ["values.yaml", "ci/b-values.yaml"],
        ])
        prod = [w for w in k8s["workloads"] if w["render"]["values"] == ["values.yaml", "values-prod.yaml"]][0]
        self.assertEqual((prod["replicas"], prod["replicas_set"]), (1, False))

    def test_identical_sets_render_once(self):
        self.chart("charts/api")
        _, renders = self.renders(helm_values="values.yaml", helm_values_chains="all")
        self.assertEqual(renders, [("charts/api", ["values.yaml"], False, True)])

    def test_autoscalers_and_crd_gated_objects(self):
        self.chart("charts/api", values=VALUES.replace("autoscaling: false", "autoscaling: true"),
                   templates={"deployment.yaml": DEPLOYMENT, "hpa.yaml": HPA, "scaledobject.yaml": SCALED_OBJECT})
        k8s, _ = self.renders(helm_values="values.yaml")
        self.assertEqual(k8s["scaled_objects"], [])
        self.assertEqual([(h["path"], h["target_workload"], h["target_kind"], h["min_replicas"], h["max_replicas"])
                          for h in k8s["hpas"]], [("charts/api/templates/hpa.yaml", "api", "Deployment", 2, 6)])
        os.remove(self.capture)
        k8s, _ = self.renders(helm_values="values.yaml", helm_api_versions="keda.sh/v1alpha1")
        self.assertEqual(k8s["scaled_objects"], [{
            "name": "api", "namespace": "default", "path": "charts/api/templates/scaledobject.yaml",
            "render": {"chart": "charts/api", "values": ["values.yaml"]},
            "target_workload": "api", "target_kind": "Deployment", "min_replicas": 2, "max_replicas": 20}])

    def test_library_charts_are_not_rendered(self):
        self.chart("charts/common", extra="type: library\n", templates={"_helpers.tpl": "{{- define \"x\" -}}x{{- end -}}\n"})
        self.assertEqual(self.collect(), {})

    def test_a_subchart_renders_with_its_parent(self):
        self.chart("charts/app")
        self.chart("charts/app/charts/sidecar")
        k8s, renders = self.renders(helm_values="values.yaml")
        self.assertEqual(renders, [("charts/app", ["values.yaml"], False, True)])
        self.assertEqual(sorted(w["path"] for w in k8s["workloads"]),
                         ["charts/app/charts/sidecar/templates/deployment.yaml", "charts/app/templates/deployment.yaml"])

    def test_a_local_file_dependency_is_built(self):
        self.chart("charts/base")
        self.chart("charts/app", templates={}, extra=(
            "dependencies:\n  - name: base\n    version: 0.1.0\n    repository: file://../base\n"))
        k8s, renders = self.renders(helm_values="values.yaml")
        self.assertEqual(renders, [("charts/app", ["values.yaml"], False, True), ("charts/base", ["values.yaml"], False, True)])
        self.assertIn("charts/app/charts/base/templates/deployment.yaml", [w["path"] for w in k8s["workloads"]])

    def test_a_missing_remote_dependency_fails_valid_with_helms_error(self):
        self.chart("charts/reports", extra=(
            "dependencies:\n  - name: postgresql\n    version: 12.0.0\n    repository: https://charts.example.com\n"))
        k8s, renders = self.renders(helm_values="values.yaml")
        self.assertEqual(renders, [("charts/reports", ["values.yaml"], False, False)])
        error = k8s["manifests"][0]["error"]
        self.assertTrue(error.startswith("helm template: "), error)
        self.assertIn("postgresql", error)
        self.assertEqual(k8s["workloads"], [])

    def test_schema_errors_name_the_chart_template(self):
        self.chart("charts/api")
        open(self.kubeconform_fails, "w").close()
        k8s, renders = self.renders(helm_values="values.yaml")
        self.assertEqual(renders, [("charts/api", ["values.yaml"], False, False)])
        self.assertTrue(k8s["manifests"][0]["error"].startswith("charts/api/templates/deployment.yaml - "),
                        k8s["manifests"][0]["error"])
        # A build-only render is only checked to build.
        os.remove(self.capture)
        _, renders = self.renders()
        self.assertEqual(renders, [("charts/api", ["values.yaml"], True, True)])

    def test_a_chart_at_the_repository_root(self):
        self.chart(".", name="svc")
        k8s, renders = self.renders(helm_values="values.yaml")
        self.assertEqual(renders, [(".", ["values.yaml"], False, True)])
        self.assertEqual((k8s["workloads"][0]["path"], k8s["workloads"][0]["name"]), ("templates/deployment.yaml", "svc"))

    def test_without_helm_the_run_fails_instead_of_failing_every_chart(self):
        self.chart("charts/api")
        env = dict(os.environ, PATH=self.bin + os.pathsep + "/usr/bin:/bin")
        proc = subprocess.run(["bash", RENDER_SH], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("helm is not installed", proc.stderr)
        self.assertFalse(os.path.exists(self.capture))

    def test_an_unknown_chains_mode_fails_loudly(self):
        self.chart("charts/api")
        proc = self.run_script(RENDER_SH, helm_values_chains="true")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("helm_values_chains must be", proc.stderr)


class WorkloadFieldsTest(Harness):
    def test_static_manifest_fields(self):
        self.write("deploy/app.yaml", textwrap.dedent("""\
            apiVersion: apps/v1
            kind: Deployment
            metadata:
              name: api
              namespace: payments
            spec:
              replicas: 3
              selector:
                matchLabels: {app: api}
              template:
                metadata:
                  labels: {app: api}
                  annotations: {prometheus.io/scrape: "true"}
                spec:
                  terminationGracePeriodSeconds: 45
                  topologySpreadConstraints:
                    - topologyKey: topology.kubernetes.io/zone
                      maxSkew: 1
                      labelSelector: {matchLabels: {app: api}}
                  initContainers:
                    - name: migrate
                      image: ghcr.io/acme/migrate:1
                  containers:
                    - name: api
                      image: ghcr.io/acme/api:1
                      lifecycle:
                        preStop:
                          sleep: {seconds: 5}
                      livenessProbe:
                        httpGet: {port: 8080, path: /livez}
                        timeoutSeconds: 2
                      readinessProbe:
                        exec:
                          command: [cat, /tmp/ready]
                        periodSeconds: 5
            ---
            apiVersion: keda.sh/v1alpha1
            kind: ScaledObject
            metadata:
              name: worker
              namespace: payments
            spec:
              scaleTargetRef: {name: worker}
              triggers: [{type: cpu, metadata: {value: "50"}}]
            """))
        k8s = self.collect(MAIN_SH)[".k8s"]
        w = k8s["workloads"][0]
        self.assertEqual({k: w[k] for k in ("replicas", "replicas_set", "pod_annotations", "termination_grace_period_seconds")},
                         {"replicas": 3, "replicas_set": True, "pod_annotations": {"prometheus.io/scrape": "true"},
                          "termination_grace_period_seconds": 45})
        self.assertNotIn("render", w)
        self.assertEqual(w["topology_spread_constraints"], [{
            "topology_key": "topology.kubernetes.io/zone", "max_skew": 1, "when_unsatisfiable": "DoNotSchedule",
            "label_selector": {"matchLabels": {"app": "api"}}, "match_label_keys": []}])
        api = w["containers"][0]
        self.assertTrue(api["has_prestop"])
        self.assertEqual(api["liveness_probe"], {"handler": "httpGet", "port": 8080, "path": "/livez",
                                                 "initial_delay_seconds": 0, "period_seconds": 10,
                                                 "timeout_seconds": 2, "failure_threshold": 3})
        self.assertEqual(api["readiness_probe"], {"handler": "exec", "port": None, "path": None,
                                                  "initial_delay_seconds": 0, "period_seconds": 5, "timeout_seconds": 1,
                                                  "failure_threshold": 3, "command": ["cat", "/tmp/ready"]})
        self.assertIsNone(api["startup_probe"])
        self.assertEqual([(c["name"], c["image"], c["has_prestop"]) for c in w["init_containers"]],
                         [("migrate", "ghcr.io/acme/migrate:1", False)])
        self.assertEqual(k8s["scaled_objects"], [{
            "name": "worker", "namespace": "payments", "path": "deploy/app.yaml", "target_workload": "worker",
            "target_kind": "Deployment", "min_replicas": 0, "max_replicas": 100}])
        self.assertEqual(k8s["manifests"][0]["resources"], [
            {"kind": "Deployment", "name": "api", "namespace": "payments", "api_version": "apps/v1"},
            {"kind": "ScaledObject", "name": "worker", "namespace": "payments", "api_version": "keda.sh/v1alpha1"}])

    def test_unset_fields_take_kubernetes_defaults(self):
        self.write("deploy/job.yaml", textwrap.dedent("""\
            apiVersion: batch/v1
            kind: Job
            metadata:
              name: once
            spec:
              template:
                spec:
                  containers:
                    - name: run
                      image: busybox
            """))
        w = self.collect(MAIN_SH)[".k8s"]["workloads"][0]
        self.assertEqual((w["replicas"], w["replicas_set"], w["termination_grace_period_seconds"],
                          w["topology_spread_constraints"], w["pod_annotations"], w["init_containers"]),
                         (1, False, 30, [], {}, []))


if __name__ == "__main__":
    unittest.main()
