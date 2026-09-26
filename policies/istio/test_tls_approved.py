"""Unit tests for the istio tls-approved check.

Fixtures use the shape the istio collector writes (collectors/istio/test pins
that side against manifests istioctl validates).
"""

import importlib
import os
import re
import unittest
from unittest import mock

from lunar_policy import CheckStatus, Node

from tls_approved import main as check_tls

VERSIONS = "TLSV1_2,TLSV1_3"
SUITES = "ECDHE-ECDSA-AES256-GCM-SHA384, ECDHE-RSA-AES256-GCM-SHA384"
GOOD_CIPHERS = ["ECDHE-ECDSA-AES256-GCM-SHA384", "ECDHE-RSA-AES256-GCM-SHA384"]


def server(port=443, mode="SIMPLE", min_version=None, max_version=None, ciphers=None, protocol="HTTPS"):
    return {"port": port, "protocol": protocol, "tls_mode": mode, "https_redirect": False,
            "min_protocol_version": min_version, "max_protocol_version": max_version, "cipher_suites": ciphers}


def gateway(*servers, name="ingress", namespace="istio-system"):
    return {"name": name, "namespace": namespace, "path": "istio/gateway.yaml", "servers": list(servers)}


def mesh_config(mtls_min=None, mtls_ciphers=None, defaults_min=None, defaults_ciphers=None,
                kind="IstioOperator", name="control-plane"):
    return {"kind": kind, "name": name, "namespace": "istio-system", "path": "istio/operator.yaml",
            "mesh_mtls": {"min_protocol_version": mtls_min, "cipher_suites": mtls_ciphers},
            "tls_defaults": {"min_protocol_version": defaults_min, "cipher_suites": defaults_ciphers}}


def run(gateways=(), mesh_configs=(), versions=VERSIONS, suites=SUITES, mesh=True, finished=True):
    data = {"mesh": {"provider": "istio", "gateways": list(gateways), "mesh_configs": list(mesh_configs)}} if mesh else {}
    env = {k: v for k, v in (("LUNAR_VAR_approved_tls_versions", versions),
                             ("LUNAR_VAR_approved_cipher_suites", suites)) if v is not None}
    with mock.patch.dict(os.environ, env):
        return check_tls(Node.from_component_json(data, {"workflows_finished": finished}))


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def skipped(check):
    return any(r.result == CheckStatus.SKIPPED for r in check._results)


class GatewayServerTest(unittest.TestCase):
    def test_pinned_approved_server_passes(self):
        check = run([gateway(server(min_version="TLSV1_2", max_version="TLSV1_3", ciphers=GOOD_CIPHERS))])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_floor_below_the_approved_versions_fails(self):
        check = run([gateway(server(min_version="TLSV1_0", ciphers=GOOD_CIPHERS))])
        self.assertEqual(failures(check), [
            "Gateway istio-system/ingress port 443 (SIMPLE) allows unapproved protocol versions TLSV1_0, TLSV1_1"])

    def test_unset_ceiling_is_tls_1_3(self):
        # An organisation that approves only TLS 1.2 must pin the ceiling too.
        check = run([gateway(server(min_version="TLSV1_2", ciphers=GOOD_CIPHERS))], versions="TLSV1_2")
        self.assertEqual(failures(check), [
            "Gateway istio-system/ingress port 443 (SIMPLE) allows unapproved protocol versions TLSV1_3"])
        pinned = run([gateway(server(min_version="TLSV1_2", max_version="TLSV1_2", ciphers=GOOD_CIPHERS))],
                     versions="TLSV1_2")
        self.assertEqual(pinned.status, CheckStatus.PASS, failures(pinned))

    def test_unset_values_fail(self):
        check = run([gateway(server(mode="MUTUAL"))])
        self.assertEqual(failures(check), [
            "Gateway istio-system/ingress port 443 (MUTUAL) doesn't set minProtocolVersion (on the server or in "
            "meshConfig.tlsDefaults); doesn't set cipherSuites (on the server or in meshConfig.tlsDefaults)"])

    def test_tls_auto_does_not_set_a_floor(self):
        check = run([gateway(server(min_version="TLS_AUTO", ciphers=GOOD_CIPHERS))])
        self.assertIn("doesn't set minProtocolVersion", failures(check)[0])

    def test_unapproved_cipher_fails(self):
        check = run([gateway(server(min_version="TLSV1_2", ciphers=GOOD_CIPHERS + ["AES128-SHA", "DES-CBC3-SHA"]))])
        self.assertEqual(failures(check), [
            "Gateway istio-system/ingress port 443 (SIMPLE) uses unapproved cipher suites AES128-SHA, DES-CBC3-SHA"])

    def test_tls_1_3_floor_needs_no_cipher_suites(self):
        # cipherSuites don't apply to TLS 1.3, so neither unset nor unapproved ones matter.
        for ciphers in (None, ["AES128-SHA"]):
            check = run([gateway(server(min_version="TLSV1_3", ciphers=ciphers))])
            self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_cipher_names_compare_case_insensitively(self):
        check = run([gateway(server(min_version="TLSV1_2", ciphers=["ecdhe-rsa-aes256-gcm-sha384"]))])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_servers_that_do_not_terminate_tls_are_out_of_scope(self):
        check = run([gateway(server(mode="PASSTHROUGH"), server(port=15443, mode="AUTO_PASSTHROUGH"),
                             server(port=15012, mode="ISTIO_MUTUAL"), server(port=80, mode=None, protocol="HTTP"))])
        self.assertTrue(skipped(check))

    def test_optional_mutual_is_checked(self):
        self.assertEqual(run([gateway(server(mode="OPTIONAL_MUTUAL"))]).status, CheckStatus.FAIL)

    def test_only_one_list_configured_checks_only_that_half(self):
        s = server(min_version="TLSV1_0")  # no ciphers
        self.assertEqual(failures(run([gateway(s)], suites=None)), [
            "Gateway istio-system/ingress port 443 (SIMPLE) allows unapproved protocol versions TLSV1_0, TLSV1_1"])
        self.assertEqual(failures(run([gateway(s)], versions=None)), [
            "Gateway istio-system/ingress port 443 (SIMPLE) doesn't set cipherSuites (on the server or in "
            "meshConfig.tlsDefaults)"])


class InheritanceTest(unittest.TestCase):
    def test_server_inherits_tls_defaults(self):
        check = run([gateway(server())], [mesh_config(mtls_min="TLSV1_3", defaults_min="TLSV1_2",
                                                      defaults_ciphers=GOOD_CIPHERS)])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_server_values_override_tls_defaults(self):
        check = run([gateway(server(min_version="TLSV1_0"))],
                    [mesh_config(mtls_min="TLSV1_3", defaults_min="TLSV1_2", defaults_ciphers=GOOD_CIPHERS)])
        self.assertEqual(failures(check), [
            "Gateway istio-system/ingress port 443 (SIMPLE) allows unapproved protocol versions TLSV1_0, TLSV1_1"])

    def test_with_several_mesh_configs_only_what_all_set_is_inherited(self):
        full = mesh_config(mtls_min="TLSV1_3", defaults_min="TLSV1_2", defaults_ciphers=GOOD_CIPHERS)
        partial = mesh_config(mtls_min="TLSV1_3", name="canary")
        check = run([gateway(server())], [full, partial])
        self.assertEqual(len(failures(check)), 1)
        self.assertIn("doesn't set minProtocolVersion", failures(check)[0])
        # The lowest floor any of them sets is the one a server may end up with.
        strict = mesh_config(mtls_min="TLSV1_3", defaults_min="TLSV1_3", defaults_ciphers=GOOD_CIPHERS)
        lenient = mesh_config(mtls_min="TLSV1_3", defaults_min="TLSV1_2", defaults_ciphers=GOOD_CIPHERS, name="canary")
        lowest = run([gateway(server())], [strict, lenient], versions="TLSV1_3")
        self.assertIn("Gateway istio-system/ingress port 443 (SIMPLE) allows unapproved protocol versions TLSV1_2",
                      failures(lowest))


class MeshConfigTest(unittest.TestCase):
    def test_approved_mesh_config_passes(self):
        check = run(mesh_configs=[mesh_config(mtls_min="TLSV1_2", mtls_ciphers=GOOD_CIPHERS)])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_mesh_mtls_tls_1_3_floor_needs_no_ciphers(self):
        check = run(mesh_configs=[mesh_config(mtls_min="TLSV1_3")])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_mesh_mtls_must_set_its_floor(self):
        check = run(mesh_configs=[mesh_config(kind="ConfigMap", name="istio")])
        self.assertEqual(failures(check), [
            "ConfigMap istio-system/istio meshConfig.meshMTLS doesn't set minProtocolVersion; doesn't set cipherSuites"])

    def test_mesh_mtls_unapproved_values_fail(self):
        check = run(mesh_configs=[mesh_config(mtls_min="TLSV1_2", mtls_ciphers=["AES256-GCM-SHA384"])],
                    versions="TLSV1_3")
        self.assertEqual(failures(check), [
            "IstioOperator istio-system/control-plane meshConfig.meshMTLS allows unapproved protocol versions "
            "TLSV1_2; uses unapproved cipher suites AES256-GCM-SHA384"])

    def test_tls_defaults_values_are_checked_when_set(self):
        check = run(mesh_configs=[mesh_config(mtls_min="TLSV1_3", defaults_min="TLSV1_2",
                                              defaults_ciphers=["AES128-GCM-SHA256"])], versions="TLSV1_3")
        self.assertEqual(failures(check), [
            "IstioOperator istio-system/control-plane meshConfig.tlsDefaults allows unapproved protocol versions "
            "TLSV1_2; uses unapproved cipher suites AES128-GCM-SHA256"])

    def test_tls_defaults_ciphers_are_checked_without_a_floor(self):
        check = run(mesh_configs=[mesh_config(mtls_min="TLSV1_3", defaults_ciphers=["AES128-GCM-SHA256"])])
        self.assertEqual(failures(check), [
            "IstioOperator istio-system/control-plane meshConfig.tlsDefaults uses unapproved cipher suites "
            "AES128-GCM-SHA256"])

    def test_unset_tls_defaults_is_fine(self):
        check = run(mesh_configs=[mesh_config(mtls_min="TLSV1_3")])
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))


class ConfigurationTest(unittest.TestCase):
    def test_no_approved_lists_skips(self):
        check = run([gateway(server(min_version="TLSV1_0"))], versions=None, suites=None)
        self.assertTrue(skipped(check))
        self.assertEqual(failures(check), [])

    def test_blank_lists_skip(self):
        self.assertTrue(skipped(run([gateway(server(min_version="TLSV1_0"))], versions=" ", suites="")))

    def test_block_style_lists_parse(self):
        check = run([gateway(server(min_version="TLSV1_2", ciphers=GOOD_CIPHERS))],
                    versions="TLSV1_2\nTLSV1_3\n", suites="ECDHE-ECDSA-AES256-GCM-SHA384\nECDHE-RSA-AES256-GCM-SHA384\n")
        self.assertEqual(check.status, CheckStatus.PASS, failures(check))

    def test_unknown_version_name_is_a_misconfiguration(self):
        with self.assertRaises(ValueError) as ctx:
            run([gateway(server(min_version="TLSV1_2"))], versions="TLSv1.2")
        self.assertIn("misconfiguration", str(ctx.exception))

    def test_no_tls_terminating_config_skips(self):
        self.assertTrue(skipped(run([gateway(server(port=80, mode=None, protocol="HTTP"))])))
        self.assertTrue(skipped(run()))

    def test_no_mesh_skips(self):
        self.assertTrue(skipped(run(mesh=False)))

    def test_pending_while_collection_runs(self):
        self.assertEqual(run(mesh=False, finished=False).status, CheckStatus.PENDING)


class HarnessTest(unittest.TestCase):
    """Every check in the manifest resolves on a component with no mesh data."""

    def test_every_check_skips_without_mesh_data_and_pends_during_collection(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lunar-policy.yml")) as fh:
            modules = re.findall(r"mainPython:\s*(\w+)\.py", fh.read())
        self.assertIn("tls_approved", modules)
        for module in modules:
            main = importlib.import_module(module).main
            done = main(Node.from_component_json({}, {"workflows_finished": True}))
            self.assertTrue(skipped(done), module)
            running = main(Node.from_component_json({}, {"workflows_finished": False}))
            self.assertEqual(running.status, CheckStatus.PENDING, module)


if __name__ == "__main__":
    unittest.main()
