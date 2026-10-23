"""NetworkPolicy collection tests for the k8s collector.

These write real manifests to a scratch repo, stub `lunar` (to capture what is
collected) and `kubeconform` (it fetches schemas over the network), and run the
real main.sh with the image's yq, jq and parallel. Manifests are kept inline so
the repository itself carries no Kubernetes YAML for the collector to find.
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

# Verbatim from the Kubernetes docs examples:
# https://github.com/kubernetes/website/tree/main/content/en/examples/service/networking
DOCS_EXAMPLES = {
    "networkpolicy.yaml": """\
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: test-network-policy
  namespace: default
spec:
  podSelector:
    matchLabels:
      role: db
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - ipBlock:
        cidr: 172.17.0.0/16
        except:
        - 172.17.1.0/24
    - namespaceSelector:
        matchLabels:
          project: myproject
    - podSelector:
        matchLabels:
          role: frontend
    ports:
    - protocol: TCP
      port: 6379
  egress:
  - to:
    - ipBlock:
        cidr: 10.0.0.0/24
    ports:
    - protocol: TCP
      port: 5978
""",
    "network-policy-default-deny-egress.yaml": """\
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
spec:
  podSelector: {}
  policyTypes:
  - Egress
""",
    "network-policy-allow-all-egress.yaml": """\
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-all-egress
spec:
  podSelector: {}
  egress:
  - {}
  policyTypes:
  - Egress
""",
    "network-policy-default-deny-ingress.yaml": """\
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}
  policyTypes:
  - Ingress
""",
    "networkpolicy-multiport-egress.yaml": """\
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: multi-port-egress
  namespace: default
spec:
  podSelector:
    matchLabels:
      role: db
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: 10.0.0.0/24
      ports:
        - protocol: TCP
          port: 32000
          endPort: 32768
""",
}


class NetworkPolicyTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.bin = tempfile.mkdtemp()
        self.capture = os.path.join(self.bin, "captured.jsonl")
        stubs = {
            # `lunar collect -j <path> -` -> one JSON line per call.
            "lunar": f"""\
                #!/bin/bash
                [ "$1" = "collect" ] || exit 0
                shift; [ "$1" = "-j" ] && shift
                jq -c --arg path "$1" '{{path: $path, value: .}}' >> {self.capture}
                """,
            "kubeconform": """\
                #!/bin/bash
                [ "$1" = "-v" ] && echo "v0.8.0"
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

    def collect(self):
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"])
        proc = subprocess.run(["bash", MAIN_SH], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not os.path.exists(self.capture):
            return {}
        with open(self.capture) as fh:
            return {rec["path"]: rec["value"] for rec in map(json.loads, fh)}

    def policies(self):
        return sorted(self.collect()[".k8s"]["network_policies"], key=lambda p: p["name"])

    def test_docs_examples_are_recorded_as_written(self):
        for name, body in DOCS_EXAMPLES.items():
            self.write(f"deploy/{name}", body)
        self.assertEqual(self.policies(), [
            {"name": "allow-all-egress", "namespace": "default", "path": "deploy/network-policy-allow-all-egress.yaml",
             "pod_selector": {}, "policy_types": ["Egress"], "egress": [{}]},
            {"name": "default-deny-egress", "namespace": "default",
             "path": "deploy/network-policy-default-deny-egress.yaml",
             "pod_selector": {}, "policy_types": ["Egress"], "egress": []},
            {"name": "default-deny-ingress", "namespace": "default",
             "path": "deploy/network-policy-default-deny-ingress.yaml",
             "pod_selector": {}, "policy_types": ["Ingress"], "egress": []},
            {"name": "multi-port-egress", "namespace": "default", "path": "deploy/networkpolicy-multiport-egress.yaml",
             "pod_selector": {"matchLabels": {"role": "db"}}, "policy_types": ["Egress"],
             "egress": [{"to": [{"ipBlock": {"cidr": "10.0.0.0/24"}}],
                         "ports": [{"protocol": "TCP", "port": 32000, "endPort": 32768}]}]},
            {"name": "test-network-policy", "namespace": "default", "path": "deploy/networkpolicy.yaml",
             "pod_selector": {"matchLabels": {"role": "db"}}, "policy_types": ["Ingress", "Egress"],
             "egress": [{"to": [{"ipBlock": {"cidr": "10.0.0.0/24"}}], "ports": [{"protocol": "TCP", "port": 5978}]}]},
        ])

    def test_unset_policy_types_default_like_the_api_server(self):
        # Ingress always; Egress only when there is at least one egress rule.
        self.write("netpol.yaml", textwrap.dedent("""\
            apiVersion: networking.k8s.io/v1
            kind: NetworkPolicy
            metadata:
              name: egress-rules
            spec:
              podSelector:
                matchLabels:
                  app: api
              egress:
                - to:
                    - ipBlock:
                        cidr: 0.0.0.0/0
                        except:
                          - 169.254.169.254/32
            ---
            apiVersion: networking.k8s.io/v1
            kind: NetworkPolicy
            metadata:
              name: ingress-rules
            spec:
              podSelector: {}
              ingress:
                - from:
                    - podSelector: {}
            ---
            apiVersion: networking.k8s.io/v1
            kind: NetworkPolicy
            metadata:
              name: empty-egress
            spec:
              egress: []
            """))
        types = {p["name"]: p["policy_types"] for p in self.policies()}
        self.assertEqual(types, {"egress-rules": ["Ingress", "Egress"], "ingress-rules": ["Ingress"],
                                 "empty-egress": ["Ingress"]})
        # An absent podSelector is the empty selector.
        self.assertEqual({p["name"]: p["pod_selector"] for p in self.policies()}["empty-egress"], {})

    def test_policy_beside_its_workload(self):
        self.write("deploy/api.yaml", textwrap.dedent("""\
            apiVersion: apps/v1
            kind: Deployment
            metadata:
              name: api
              namespace: payments
            spec:
              selector:
                matchLabels:
                  app: api
              template:
                metadata:
                  labels:
                    app: api
                spec:
                  containers:
                    - name: api
                      image: registry.example.com/api:1.0.0
            ---
            apiVersion: networking.k8s.io/v1
            kind: NetworkPolicy
            metadata:
              name: api-egress
              namespace: payments
            spec:
              podSelector:
                matchLabels:
                  app: api
              policyTypes:
                - Egress
              egress:
                - to:
                    - namespaceSelector:
                        matchLabels:
                          kubernetes.io/metadata.name: kube-system
                      podSelector:
                        matchLabels:
                          k8s-app: kube-dns
                  ports:
                    - protocol: UDP
                      port: 53
                - to:
                    - ipBlock:
                        cidr: 0.0.0.0/0
                        except:
                          - 169.254.169.254/32
                  ports:
                    - port: 443
            """))
        k8s = self.collect()[".k8s"]
        self.assertEqual([(w["kind"], w["pod_labels"]) for w in k8s["workloads"]], [("Deployment", {"app": "api"})])
        self.assertEqual(k8s["network_policies"], [{
            "name": "api-egress", "namespace": "payments", "path": "deploy/api.yaml",
            "pod_selector": {"matchLabels": {"app": "api"}}, "policy_types": ["Egress"],
            "egress": [
                {"to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
                         "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}}}],
                 "ports": [{"protocol": "UDP", "port": 53}]},
                {"to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["169.254.169.254/32"]}}],
                 "ports": [{"port": 443}]},
            ]}])

    def test_calico_network_policy_is_not_read_as_a_kubernetes_one(self):
        self.write("calico.yaml", textwrap.dedent("""\
            apiVersion: projectcalico.org/v3
            kind: NetworkPolicy
            metadata:
              name: deny-metadata
              namespace: payments
            spec:
              selector: all()
              types:
                - Egress
              egress:
                - action: Deny
                  destination:
                    nets:
                      - 169.254.169.254/32
                - action: Allow
            """))
        k8s = self.collect()[".k8s"]
        self.assertEqual(k8s["network_policies"], [])
        self.assertEqual(k8s["manifests"][0]["resources"][0]["kind"], "NetworkPolicy")

    def test_repo_without_policies_records_an_empty_list(self):
        self.write("deploy/cm.yaml", "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: settings\n")
        self.assertEqual(self.collect()[".k8s"]["network_policies"], [])

    def test_no_manifests_writes_nothing(self):
        self.write("README.md", "# not kubernetes\n")
        self.assertEqual(self.collect(), {})


if __name__ == "__main__":
    unittest.main()
