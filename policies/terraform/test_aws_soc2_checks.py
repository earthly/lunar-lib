"""Unit tests for the AWS SOC 2 checks in the terraform policy.

Run from this directory:  python3 -m unittest test_aws_soc2_checks -v

Each test builds a Component JSON node whose `.iac.native.terraform.files[].hcl`
mirrors the hcl2json shape the terraform collector produces, then asserts the
check resolves to PASS / FAIL / SKIPPED.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import Node, CheckStatus  # noqa: E402

import alb_waf_enabled
import cloudtrail_multi_region
import security_group_no_public_postgres
import security_group_no_public_ssh
import eks_control_plane_logging
import elb_access_logging
import ebs_snapshot_encryption
import ebs_volume_encryption
import elb_https_only
import guardduty_enabled
import rds_cloudwatch_logging
import s3_block_public_access
import s3_access_logging
import vpc_flow_logs


def node(resource):
    """Build a node from a {type: {name: [cfg]}} resource map."""
    return Node.from_component_json(
        {"iac": {"native": {"terraform": {"files": [
            {"path": "main.tf", "hcl": {"resource": resource}}
        ]}}}}
    )


EMPTY = Node.from_component_json({"iac": {"native": {"terraform": {"files": []}}}})


def status(mod, n):
    # The SDK's Check.status property aggregates FAIL/ERROR/PENDING but not
    # SKIPPED (a skipped check reports PASS via .status while the real runtime
    # still receives the SKIPPED result). Detect the skip from the result set.
    c = mod.main(n)
    for r in getattr(c, "_results", []):
        if r.result == CheckStatus.SKIPPED:
            return CheckStatus.SKIPPED
    return c.status


class TestAlbWaf(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_lb": {"web": [{}]},
                  "aws_wafv2_web_acl_association": {"a": [{"resource_arn": "${aws_lb.web.arn}"}]}})
        self.assertEqual(status(alb_waf_enabled, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_lb": {"web": [{}]}})
        self.assertEqual(status(alb_waf_enabled, n), CheckStatus.FAIL)

    def test_skip_internal_only(self):
        n = node({"aws_lb": {"internal": [{"internal": True}]}})
        self.assertEqual(status(alb_waf_enabled, n), CheckStatus.SKIPPED)


class TestCloudTrail(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_cloudtrail": {"t": [
            {"is_multi_region_trail": True, "cloud_watch_logs_group_arn": "${aws_cloudwatch_log_group.t.arn}"}]}})
        self.assertEqual(status(cloudtrail_multi_region, n), CheckStatus.PASS)

    def test_fail_absent(self):
        n = node({"aws_s3_bucket": {"b": [{}]}})
        self.assertEqual(status(cloudtrail_multi_region, n), CheckStatus.FAIL)

    def test_fail_not_multiregion(self):
        n = node({"aws_cloudtrail": {"t": [{"is_multi_region_trail": False}]}})
        self.assertEqual(status(cloudtrail_multi_region, n), CheckStatus.FAIL)


class TestSgPostgres(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_security_group_rule": {"r": [
            {"type": "ingress", "from_port": 5432, "to_port": 5432, "protocol": "tcp",
             "source_security_group_id": "${aws_security_group.eks.id}"}]}})
        self.assertEqual(status(security_group_no_public_postgres, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_security_group_rule": {"r": [
            {"type": "ingress", "from_port": 5432, "to_port": 5432, "protocol": "tcp",
             "cidr_blocks": ["0.0.0.0/0"]}]}})
        self.assertEqual(status(security_group_no_public_postgres, n), CheckStatus.FAIL)

    def test_skip(self):
        n = node({"aws_db_instance": {"db": [{}]}})
        self.assertEqual(status(security_group_no_public_postgres, n), CheckStatus.SKIPPED)


class TestSgSsh(unittest.TestCase):
    def test_pass_inline(self):
        n = node({"aws_security_group": {"sg": [
            {"ingress": [{"from_port": 22, "to_port": 22, "protocol": "tcp",
                          "cidr_blocks": ["10.0.0.0/8"]}]}]}})
        self.assertEqual(status(security_group_no_public_ssh, n), CheckStatus.PASS)

    def test_fail_all_ports(self):
        n = node({"aws_security_group": {"sg": [
            {"ingress": [{"protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}]}]}})
        self.assertEqual(status(security_group_no_public_ssh, n), CheckStatus.FAIL)

    def test_fail_v6(self):
        n = node({"aws_vpc_security_group_ingress_rule": {"r": [
            {"from_port": 22, "to_port": 22, "ip_protocol": "tcp", "cidr_ipv6": "::/0"}]}})
        self.assertEqual(status(security_group_no_public_ssh, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(security_group_no_public_ssh, EMPTY), CheckStatus.SKIPPED)


class TestEksLogging(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_eks_cluster": {"c": [
            {"enabled_cluster_log_types": ["api", "audit", "authenticator", "controllerManager", "scheduler"]}]}})
        self.assertEqual(status(eks_control_plane_logging, n), CheckStatus.PASS)

    def test_fail_partial(self):
        n = node({"aws_eks_cluster": {"c": [{"enabled_cluster_log_types": ["api"]}]}})
        self.assertEqual(status(eks_control_plane_logging, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(eks_control_plane_logging, EMPTY), CheckStatus.SKIPPED)


class TestElbAccessLogging(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_lb": {"l": [{"access_logs": [{"enabled": True, "bucket": "logs"}]}]}})
        self.assertEqual(status(elb_access_logging, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_lb": {"l": [{}]}})
        self.assertEqual(status(elb_access_logging, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(elb_access_logging, EMPTY), CheckStatus.SKIPPED)


class TestEbsSnapshot(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(status(ebs_snapshot_encryption,
                                 node({"aws_ebs_snapshot": {"s": [{"encrypted": True}]}})), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(ebs_snapshot_encryption,
                                 node({"aws_ebs_snapshot": {"s": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(ebs_snapshot_encryption, EMPTY), CheckStatus.SKIPPED)


class TestEbsVolume(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(status(ebs_volume_encryption,
                                 node({"aws_ebs_volume": {"v": [{"encrypted": True}]}})), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(ebs_volume_encryption,
                                 node({"aws_ebs_volume": {"v": [{"size": 100}]}})), CheckStatus.FAIL)

    def test_fail_instance_block_device(self):
        n = node({"aws_instance": {"web": [{"root_block_device": [{"volume_size": 50}]}]}})
        self.assertEqual(status(ebs_volume_encryption, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(ebs_volume_encryption, EMPTY), CheckStatus.SKIPPED)


class TestElbHttps(unittest.TestCase):
    def test_pass_https(self):
        self.assertEqual(status(elb_https_only,
                                 node({"aws_lb_listener": {"h": [{"protocol": "HTTPS"}]}})), CheckStatus.PASS)

    def test_pass_redirect(self):
        n = node({"aws_lb_listener": {"h": [
            {"protocol": "HTTP", "default_action": [
                {"type": "redirect", "redirect": [{"protocol": "HTTPS", "status_code": "HTTP_301"}]}]}]}})
        self.assertEqual(status(elb_https_only, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(elb_https_only,
                                 node({"aws_lb_listener": {"h": [{"protocol": "HTTP"}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(elb_https_only, EMPTY), CheckStatus.SKIPPED)


class TestGuardDuty(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(status(guardduty_enabled,
                                 node({"aws_guardduty_detector": {"d": [{"enable": True}]}})), CheckStatus.PASS)

    def test_fail_absent(self):
        self.assertEqual(status(guardduty_enabled,
                                 node({"aws_s3_bucket": {"b": [{}]}})), CheckStatus.FAIL)


class TestRdsLogging(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_db_instance": {"db": [{"enabled_cloudwatch_logs_exports": ["postgresql", "upgrade"]}]}})
        self.assertEqual(status(rds_cloudwatch_logging, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(rds_cloudwatch_logging,
                                 node({"aws_db_instance": {"db": [{"engine": "postgres"}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(rds_cloudwatch_logging, EMPTY), CheckStatus.SKIPPED)


class TestS3PublicAccess(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_public_access_block": {"b": [
                      {"bucket": "${aws_s3_bucket.b.id}", "block_public_acls": True,
                       "block_public_policy": True, "ignore_public_acls": True,
                       "restrict_public_buckets": True}]}})
        self.assertEqual(status(s3_block_public_access, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(s3_block_public_access,
                                 node({"aws_s3_bucket": {"b": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(s3_block_public_access, EMPTY), CheckStatus.SKIPPED)


class TestS3AccessLogging(unittest.TestCase):
    def test_pass_separate(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_logging": {"lg": [
                      {"bucket": "${aws_s3_bucket.b.id}", "target_bucket": "${aws_s3_bucket.logs.id}"}]}})
        self.assertEqual(status(s3_access_logging, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(s3_access_logging,
                                 node({"aws_s3_bucket": {"b": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(s3_access_logging, EMPTY), CheckStatus.SKIPPED)


class TestVpcFlowLogs(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_vpc": {"v": [{}]},
                  "aws_flow_log": {"f": [{"vpc_id": "${aws_vpc.v.id}"}]}})
        self.assertEqual(status(vpc_flow_logs, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(vpc_flow_logs,
                                 node({"aws_vpc": {"v": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(vpc_flow_logs, EMPTY), CheckStatus.SKIPPED)


if __name__ == "__main__":
    unittest.main()
