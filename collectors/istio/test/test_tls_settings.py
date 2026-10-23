"""TLS settings collection tests for the istio collector.

These write real manifests to a scratch repo, stub only `lunar`, and run the
real main.sh with the image's yq, jq and istioctl. Every Istio fixture is also
checked with `istioctl validate`, which parses strictly (an unknown field or enum
value is an error), so the fixtures are known to be config Istio accepts.
Manifests are kept inline so the repository carries no mesh YAML of its own.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN_SH = os.path.join(HERE, "..", "main.sh")

# The Gateway example from the Istio API reference, plus one server that pins
# its TLS protocol range and ciphers.
GATEWAY = """\
apiVersion: networking.istio.io/v1
kind: Gateway
metadata:
  name: my-gateway
  namespace: some-config-namespace
spec:
  selector:
    app: my-gateway-controller
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - uk.bookinfo.com
    - eu.bookinfo.com
    tls:
      httpsRedirect: true # sends 301 redirect for http requests
  - port:
      number: 443
      name: https-443
      protocol: HTTPS
    hosts:
    - uk.bookinfo.com
    - eu.bookinfo.com
    tls:
      mode: SIMPLE # enables HTTPS on this port
      serverCertificate: /etc/certs/servercert.pem
      privateKey: /etc/certs/privatekey.pem
  - port:
      number: 8443
      name: https-8443
      protocol: HTTPS
    hosts:
    - "api.bookinfo.com"
    tls:
      mode: MUTUAL
      credentialName: api-cert
      minProtocolVersion: TLSV1_2
      maxProtocolVersion: TLSV1_3
      cipherSuites:
      - ECDHE-ECDSA-AES256-GCM-SHA384
      - ECDHE-RSA-AES256-GCM-SHA384
"""

# The IstioOperator from Istio's "workload minimum TLS version" task, with
# tlsDefaults added.
ISTIO_OPERATOR = """\
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  name: control-plane
  namespace: istio-system
spec:
  meshConfig:
    meshMTLS:
      minProtocolVersion: TLSV1_3
    tlsDefaults:
      minProtocolVersion: TLSV1_2
      cipherSuites:
      - ECDHE-ECDSA-AES256-GCM-SHA384
      - ECDHE-RSA-AES256-GCM-SHA384
"""

# The istiod ConfigMap as `istioctl manifest generate` renders it with
# meshConfig.meshMTLS.minProtocolVersion and meshConfig.tlsDefaults.cipherSuites set.
RENDERED_CONFIGMAP = """\
apiVersion: v1
data:
  mesh: |-
    defaultConfig:
      discoveryAddress: istiod.istio-system.svc:15012
    defaultProviders:
      metrics:
      - prometheus
    enablePrometheusMerge: true
    meshMTLS:
      minProtocolVersion: TLSV1_3
    rootNamespace: istio-system
    tlsDefaults:
      cipherSuites:
      - ECDHE-ECDSA-AES256-GCM-SHA384
      - ECDHE-RSA-AES256-GCM-SHA384
    trustDomain: cluster.local
  meshNetworks: 'networks: {}'
kind: ConfigMap
metadata:
  labels:
    install.operator.istio.io/owning-resource: unknown
    istio.io/rev: default
    operator.istio.io/component: Pilot
    release: istio
  name: istio
  namespace: istio-system
"""


class TlsSettingsTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.bin = tempfile.mkdtemp()
        self.capture = os.path.join(self.bin, "captured.jsonl")
        lunar = os.path.join(self.bin, "lunar")
        with open(lunar, "w") as fh:
            fh.write(textwrap.dedent(f"""\
                #!/bin/bash
                [ "$1" = "collect" ] || exit 0
                shift; [ "$1" = "-j" ] && shift
                jq -c --arg path "$1" '{{path: $path, value: .}}' >> {self.capture}
                """))
        os.chmod(lunar, 0o755)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.bin, ignore_errors=True)

    def write(self, rel, body):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(body)
        return path

    def collect(self):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"])
        proc = subprocess.run(["bash", MAIN_SH], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not os.path.exists(self.capture):
            return {}
        with open(self.capture) as fh:
            return {rec["path"]: rec["value"] for rec in map(json.loads, fh)}

    def validate(self, body):
        path = os.path.join(self.bin, "candidate.yaml")
        with open(path, "w") as fh:
            fh.write(body)
        return subprocess.run(["istioctl", "validate", "-f", path], capture_output=True, text=True)

    def test_fixtures_are_valid_istio_config(self):
        for body in (GATEWAY, ISTIO_OPERATOR):
            proc = self.validate(body)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_validation_rejects_a_misspelled_field_or_enum(self):
        # Control for the test above. Gateways are parsed strictly. IstioOperator
        # meshConfig ignores unknown keys, but an out-of-range enum is rejected only
        # where Istio reads it, which pins the meshMTLS and tlsDefaults paths.
        for bad in (GATEWAY.replace("cipherSuites:", "cipherSuite:"),
                    GATEWAY.replace("minProtocolVersion: TLSV1_2", "minProtocolVersion: TLSV9"),
                    ISTIO_OPERATOR.replace("minProtocolVersion: TLSV1_3", "minProtocolVersion: TLSV1_1"),
                    ISTIO_OPERATOR.replace("minProtocolVersion: TLSV1_2", "minProtocolVersion: TLSV1_1")):
            self.assertNotEqual(self.validate(bad).returncode, 0, bad)

    def test_gateway_servers_record_protocol_range_and_ciphers(self):
        self.write("istio/gateway.yaml", GATEWAY)
        mesh = self.collect()[".mesh"]
        self.assertEqual(mesh["gateways"][0]["servers"], [
            {"port": 80, "protocol": "HTTP", "tls_mode": None, "https_redirect": True,
             "min_protocol_version": None, "max_protocol_version": None, "cipher_suites": None},
            {"port": 443, "protocol": "HTTPS", "tls_mode": "SIMPLE", "https_redirect": False,
             "min_protocol_version": None, "max_protocol_version": None, "cipher_suites": None},
            {"port": 8443, "protocol": "HTTPS", "tls_mode": "MUTUAL", "https_redirect": False,
             "min_protocol_version": "TLSV1_2", "max_protocol_version": "TLSV1_3",
             "cipher_suites": ["ECDHE-ECDSA-AES256-GCM-SHA384", "ECDHE-RSA-AES256-GCM-SHA384"]},
        ])
        self.assertTrue(all(r["valid"] for r in mesh["resources"]), mesh["resources"])

    def test_istio_operator_mesh_config(self):
        self.write("istio/operator.yaml", ISTIO_OPERATOR)
        self.assertEqual(self.collect()[".mesh"]["mesh_configs"], [{
            "kind": "IstioOperator", "name": "control-plane", "namespace": "istio-system",
            "path": "istio/operator.yaml",
            "mesh_mtls": {"min_protocol_version": "TLSV1_3", "cipher_suites": None},
            "tls_defaults": {"min_protocol_version": "TLSV1_2",
                             "cipher_suites": ["ECDHE-ECDSA-AES256-GCM-SHA384", "ECDHE-RSA-AES256-GCM-SHA384"]},
        }])

    def test_istio_operator_without_mesh_config_declares_none(self):
        # e.g. a gateway-only install; its settings come from the control plane's MeshConfig.
        self.write("istio/gateways.yaml", textwrap.dedent("""\
            apiVersion: install.istio.io/v1alpha1
            kind: IstioOperator
            metadata:
              name: gateways
              namespace: istio-system
            spec:
              profile: empty
            """))
        mesh = self.collect()[".mesh"]
        self.assertEqual(mesh["mesh_configs"], [])
        self.assertEqual([i["name"] for i in mesh["install"]], ["gateways"])

    def test_mesh_config_without_tls_settings_records_them_unset(self):
        self.write("istio/operator.yaml", textwrap.dedent("""\
            apiVersion: install.istio.io/v1alpha1
            kind: IstioOperator
            metadata:
              name: control-plane
              namespace: istio-system
            spec:
              meshConfig:
                accessLogFile: /dev/stdout
            """))
        unset = {"min_protocol_version": None, "cipher_suites": None}
        self.assertEqual(self.collect()[".mesh"]["mesh_configs"], [{
            "kind": "IstioOperator", "name": "control-plane", "namespace": "istio-system",
            "path": "istio/operator.yaml", "mesh_mtls": unset, "tls_defaults": unset}])

    def test_rendered_configmap_mesh_config(self):
        # A repo of rendered manifests: the ConfigMap alone is enough to collect.
        self.write("rendered/istiod-configmap.yaml", RENDERED_CONFIGMAP)
        mesh = self.collect()[".mesh"]
        self.assertEqual(mesh["mesh_configs"], [{
            "kind": "ConfigMap", "name": "istio", "namespace": "istio-system",
            "path": "rendered/istiod-configmap.yaml",
            "mesh_mtls": {"min_protocol_version": "TLSV1_3", "cipher_suites": None},
            "tls_defaults": {"min_protocol_version": None,
                             "cipher_suites": ["ECDHE-ECDSA-AES256-GCM-SHA384", "ECDHE-RSA-AES256-GCM-SHA384"]},
        }])
        self.assertEqual(mesh["resources"], [])

    def test_mesh_config_only_files_are_not_analyzed(self):
        # The ConfigMap is recorded, but istioctl analyze still sees only files
        # with Istio resources, as before mesh_configs.
        real = shutil.which("istioctl")
        log = os.path.join(self.bin, "istioctl.log")
        shim = os.path.join(self.bin, "istioctl")
        with open(shim, "w") as fh:
            fh.write(f'#!/bin/bash\necho "$*" >> {log}\nexec {real} "$@"\n')
        os.chmod(shim, 0o755)
        self.write("rendered/istiod-configmap.yaml", RENDERED_CONFIGMAP)
        self.write("istio/gateway.yaml", GATEWAY)
        mesh = self.collect()[".mesh"]
        self.assertEqual([m["path"] for m in mesh["mesh_configs"]], ["rendered/istiod-configmap.yaml"])
        with open(log) as fh:
            analyze = [line for line in fh.read().splitlines() if line.startswith("analyze")]
        self.assertEqual(len(analyze), 1, analyze)
        self.assertIn("istio/gateway.yaml", analyze[0])
        self.assertNotIn("istiod-configmap.yaml", analyze[0])

    def test_only_istiod_configmaps_are_read(self):
        revision = RENDERED_CONFIGMAP.replace("name: istio\n", "name: istio-canary\n")
        injector = textwrap.dedent("""\
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: istio-sidecar-injector
              namespace: istio-system
            data:
              values: '{}'
            """)
        other = RENDERED_CONFIGMAP.replace("name: istio\n", "name: app-settings\n")
        self.write("rendered/all.yaml", "---\n".join([revision, injector, other]))
        self.assertEqual([m["name"] for m in self.collect()[".mesh"]["mesh_configs"]], ["istio-canary"])

    def test_unparseable_mesh_string_is_skipped_without_losing_the_file(self):
        broken = RENDERED_CONFIGMAP.replace("    meshMTLS:\n", "    meshMTLS: [\n")
        self.write("rendered/all.yaml", broken + "---\n" + GATEWAY)
        mesh = self.collect()[".mesh"]
        self.assertEqual(mesh["mesh_configs"], [])
        self.assertEqual([g["name"] for g in mesh["gateways"]], ["my-gateway"])

    def test_no_istio_config_writes_nothing(self):
        self.write("deploy/cm.yaml", "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: settings\n")
        self.assertEqual(self.collect(), {})


if __name__ == "__main__":
    unittest.main()
