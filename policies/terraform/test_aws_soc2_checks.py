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

import aws_alb_waf_enabled
import aws_cloudtrail_multi_region
import aws_security_group_no_public_postgres
import aws_security_group_no_public_ssh
import aws_eks_control_plane_logging
import aws_elb_access_logging
import aws_ebs_snapshot_encryption
import aws_ebs_volume_encryption
import aws_elb_https_only
import aws_tls_policy_approved
import aws_stateful_backup_configured
import aws_guardduty_enabled
import aws_rds_cloudwatch_logging
import aws_s3_block_public_access
import aws_s3_access_logging
import aws_vpc_flow_logs
import aws_security_group_no_public_admin_ports
import aws_rds_encryption_at_rest
import aws_rds_not_publicly_accessible
import aws_rds_snapshot_encryption
import aws_s3_encryption_at_rest
import aws_s3_no_static_website
import aws_s3_no_public_acl
import aws_iam_password_min_length
import aws_iam_no_direct_user_policies
import aws_acm_cert_dns_validation
import aws_eks_private_endpoint
import aws_dynamodb_encryption
import aws_lambda_not_public
import aws_cloudtrail_log_file_validation
import aws_cloudtrail_kms_encryption
import aws_iam_role_permissions_boundary
import aws_imdsv2_required
import opentofu_state_encryption
from helpers import module_source_matches


def node(resource):
    """Build a node from a {type: {name: [cfg]}} resource map."""
    return Node.from_component_json(
        {"iac": {"native": {"terraform": {"files": [
            {"path": "main.tf", "hcl": {"resource": resource}}
        ]}}}}
    )


def node_module(module):
    """Build a node from a {name: [cfg]} module-call map."""
    return Node.from_component_json(
        {"iac": {"native": {"terraform": {"files": [
            {"path": "main.tf", "hcl": {"module": module}}
        ]}}}}
    )


def node_terraform(tf):
    """Build a node from a terraform {} block body (a list of block dicts)."""
    return Node.from_component_json(
        {"iac": {"native": {"terraform": {"files": [
            {"path": "main.tf", "hcl": {"terraform": tf}}
        ]}}}}
    )


EMPTY = Node.from_component_json({"iac": {"native": {"terraform": {"files": []}}}})


def failure_message(mod, n, **env):
    """The check's failure text — asserted where a wrong diagnosis would mislead."""
    for k, v in env.items():
        os.environ["LUNAR_VAR_" + k] = v
    try:
        c = mod.main(n)
    finally:
        for k in env:
            os.environ.pop("LUNAR_VAR_" + k, None)
    return " ".join(r.failure_message or "" for r in getattr(c, "_results", []))


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
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_lb": {"web": [{}]}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.FAIL)

    def test_skip_internal_only(self):
        n = node({"aws_lb": {"internal": [{"internal": True}]}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.SKIPPED)

    def test_fail_substring_collision(self):
        # ALB "web" has no WAF; "web2" does. "web" must still FAIL (no substring match).
        n = node({"aws_lb": {"web": [{}], "web2": [{}]},
                  "aws_wafv2_web_acl_association": {"a": [{"resource_arn": "${aws_lb.web2.arn}"}]}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.FAIL)


class TestCloudTrail(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_cloudtrail": {"t": [
            {"is_multi_region_trail": True, "cloud_watch_logs_group_arn": "${aws_cloudwatch_log_group.t.arn}"}]}})
        self.assertEqual(status(aws_cloudtrail_multi_region, n), CheckStatus.PASS)

    def test_fail_absent(self):
        n = node({"aws_s3_bucket": {"b": [{}]}})
        self.assertEqual(status(aws_cloudtrail_multi_region, n), CheckStatus.FAIL)

    def test_fail_not_multiregion(self):
        n = node({"aws_cloudtrail": {"t": [{"is_multi_region_trail": False}]}})
        self.assertEqual(status(aws_cloudtrail_multi_region, n), CheckStatus.FAIL)


class TestSgPostgres(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_security_group_rule": {"r": [
            {"type": "ingress", "from_port": 5432, "to_port": 5432, "protocol": "tcp",
             "source_security_group_id": "${aws_security_group.eks.id}"}]}})
        self.assertEqual(status(aws_security_group_no_public_postgres, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_security_group_rule": {"r": [
            {"type": "ingress", "from_port": 5432, "to_port": 5432, "protocol": "tcp",
             "cidr_blocks": ["0.0.0.0/0"]}]}})
        self.assertEqual(status(aws_security_group_no_public_postgres, n), CheckStatus.FAIL)

    def test_skip(self):
        n = node({"aws_db_instance": {"db": [{}]}})
        self.assertEqual(status(aws_security_group_no_public_postgres, n), CheckStatus.SKIPPED)


class TestSgSsh(unittest.TestCase):
    def test_pass_inline(self):
        n = node({"aws_security_group": {"sg": [
            {"ingress": [{"from_port": 22, "to_port": 22, "protocol": "tcp",
                          "cidr_blocks": ["10.0.0.0/8"]}]}]}})
        self.assertEqual(status(aws_security_group_no_public_ssh, n), CheckStatus.PASS)

    def test_fail_all_ports(self):
        n = node({"aws_security_group": {"sg": [
            {"ingress": [{"protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}]}]}})
        self.assertEqual(status(aws_security_group_no_public_ssh, n), CheckStatus.FAIL)

    def test_fail_v6(self):
        n = node({"aws_vpc_security_group_ingress_rule": {"r": [
            {"from_port": 22, "to_port": 22, "ip_protocol": "tcp", "cidr_ipv6": "::/0"}]}})
        self.assertEqual(status(aws_security_group_no_public_ssh, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_security_group_no_public_ssh, EMPTY), CheckStatus.SKIPPED)


class TestEksLogging(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_eks_cluster": {"c": [
            {"enabled_cluster_log_types": ["api", "audit", "authenticator", "controllerManager", "scheduler"]}]}})
        self.assertEqual(status(aws_eks_control_plane_logging, n), CheckStatus.PASS)

    def test_fail_partial(self):
        n = node({"aws_eks_cluster": {"c": [{"enabled_cluster_log_types": ["api"]}]}})
        self.assertEqual(status(aws_eks_control_plane_logging, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_eks_control_plane_logging, EMPTY), CheckStatus.SKIPPED)

    def test_pass_module(self):
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws",
                                  "cluster_enabled_log_types": ["api", "audit", "authenticator",
                                                                "controllerManager", "scheduler"]}]})
        self.assertEqual(status(aws_eks_control_plane_logging, n), CheckStatus.PASS)

    def test_fail_module_default(self):
        # module default (api/audit/authenticator) is missing controllerManager + scheduler
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws"}]})
        self.assertEqual(status(aws_eks_control_plane_logging, n), CheckStatus.FAIL)


class TestElbAccessLogging(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_lb": {"l": [{"access_logs": [{"enabled": True, "bucket": "logs"}]}]}})
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_lb": {"l": [{}]}})
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_elb_access_logging, EMPTY), CheckStatus.SKIPPED)

    def test_fail_lb_bucket_no_enabled(self):
        # aws_lb access_logs.enabled defaults to false even with a bucket.
        n = node({"aws_lb": {"l": [{"access_logs": [{"bucket": "logs"}]}]}})
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.FAIL)

    def test_pass_elb_bucket_no_enabled(self):
        # classic aws_elb access_logs defaults to enabled when the block is present.
        n = node({"aws_elb": {"l": [{"access_logs": [{"bucket": "logs"}]}]}})
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.PASS)


class TestEbsSnapshot(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(status(aws_ebs_snapshot_encryption,
                                 node({"aws_ebs_snapshot": {"s": [{"encrypted": True}]}})), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(aws_ebs_snapshot_encryption,
                                 node({"aws_ebs_snapshot": {"s": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_ebs_snapshot_encryption, EMPTY), CheckStatus.SKIPPED)


class TestEbsVolume(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(status(aws_ebs_volume_encryption,
                                 node({"aws_ebs_volume": {"v": [{"encrypted": True}]}})), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(aws_ebs_volume_encryption,
                                 node({"aws_ebs_volume": {"v": [{"size": 100}]}})), CheckStatus.FAIL)

    def test_fail_instance_block_device(self):
        n = node({"aws_instance": {"web": [{"root_block_device": [{"volume_size": 50}]}]}})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_ebs_volume_encryption, EMPTY), CheckStatus.SKIPPED)


class TestElbHttps(unittest.TestCase):
    def test_pass_https(self):
        self.assertEqual(status(aws_elb_https_only,
                                 node({"aws_lb_listener": {"h": [{"protocol": "HTTPS"}]}})), CheckStatus.PASS)

    def test_pass_redirect(self):
        n = node({"aws_lb_listener": {"h": [
            {"protocol": "HTTP", "default_action": [
                {"type": "redirect", "redirect": [{"protocol": "HTTPS", "status_code": "HTTP_301"}]}]}]}})
        self.assertEqual(status(aws_elb_https_only, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(aws_elb_https_only,
                                 node({"aws_lb_listener": {"h": [{"protocol": "HTTP"}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_elb_https_only, EMPTY), CheckStatus.SKIPPED)


class TestGuardDuty(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(status(aws_guardduty_enabled,
                                 node({"aws_guardduty_detector": {"d": [{"enable": True}]}})), CheckStatus.PASS)

    def test_fail_absent(self):
        self.assertEqual(status(aws_guardduty_enabled,
                                 node({"aws_s3_bucket": {"b": [{}]}})), CheckStatus.FAIL)


class TestRdsLogging(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_db_instance": {"db": [{"enabled_cloudwatch_logs_exports": ["postgresql", "upgrade"]}]}})
        self.assertEqual(status(aws_rds_cloudwatch_logging, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(aws_rds_cloudwatch_logging,
                                 node({"aws_db_instance": {"db": [{"engine": "postgres"}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_rds_cloudwatch_logging, EMPTY), CheckStatus.SKIPPED)

    def test_pass_module(self):
        n = node_module({"db": [{"source": "terraform-aws-modules/rds/aws",
                                 "enabled_cloudwatch_logs_exports": ["postgresql"]}]})
        self.assertEqual(status(aws_rds_cloudwatch_logging, n), CheckStatus.PASS)

    def test_fail_module(self):
        n = node_module({"db": [{"source": "terraform-aws-modules/rds/aws"}]})
        self.assertEqual(status(aws_rds_cloudwatch_logging, n), CheckStatus.FAIL)


class TestS3PublicAccess(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_public_access_block": {"b": [
                      {"bucket": "${aws_s3_bucket.b.id}", "block_public_acls": True,
                       "block_public_policy": True, "ignore_public_acls": True,
                       "restrict_public_buckets": True}]}})
        self.assertEqual(status(aws_s3_block_public_access, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(aws_s3_block_public_access,
                                 node({"aws_s3_bucket": {"b": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_s3_block_public_access, EMPTY), CheckStatus.SKIPPED)


class TestS3AccessLogging(unittest.TestCase):
    def test_pass_separate(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_logging": {"lg": [
                      {"bucket": "${aws_s3_bucket.b.id}", "target_bucket": "${aws_s3_bucket.logs.id}"}]}})
        self.assertEqual(status(aws_s3_access_logging, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(aws_s3_access_logging,
                                 node({"aws_s3_bucket": {"b": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_s3_access_logging, EMPTY), CheckStatus.SKIPPED)


class TestVpcFlowLogs(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_vpc": {"v": [{}]},
                  "aws_flow_log": {"f": [{"vpc_id": "${aws_vpc.v.id}"}]}})
        self.assertEqual(status(aws_vpc_flow_logs, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(aws_vpc_flow_logs,
                                 node({"aws_vpc": {"v": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_vpc_flow_logs, EMPTY), CheckStatus.SKIPPED)

    def test_pass_module(self):
        n = node_module({"vpc": [{"source": "terraform-aws-modules/vpc/aws", "enable_flow_log": True}]})
        self.assertEqual(status(aws_vpc_flow_logs, n), CheckStatus.PASS)

    def test_fail_module(self):
        n = node_module({"vpc": [{"source": "terraform-aws-modules/vpc/aws"}]})
        self.assertEqual(status(aws_vpc_flow_logs, n), CheckStatus.FAIL)


class TestSgAdminPorts(unittest.TestCase):
    def test_pass_restricted(self):
        n = node({"aws_security_group": {"db": [
            {"ingress": [{"from_port": 3306, "to_port": 3306, "protocol": "tcp",
                          "cidr_blocks": ["10.0.0.0/8"]}]}]}})
        self.assertEqual(status(aws_security_group_no_public_admin_ports, n), CheckStatus.PASS)

    def test_fail_public_rdp(self):
        n = node({"aws_security_group": {"win": [
            {"ingress": [{"from_port": 3389, "to_port": 3389, "protocol": "tcp",
                          "cidr_blocks": ["0.0.0.0/0"]}]}]}})
        self.assertEqual(status(aws_security_group_no_public_admin_ports, n), CheckStatus.FAIL)

    def test_fail_public_mysql_v6(self):
        n = node({"aws_vpc_security_group_ingress_rule": {"r": [
            {"from_port": 3306, "to_port": 3306, "ip_protocol": "tcp", "cidr_ipv6": "::/0"}]}})
        self.assertEqual(status(aws_security_group_no_public_admin_ports, n), CheckStatus.FAIL)

    def test_pass_ssh_not_double_counted(self):
        # SSH (22) is owned by the dedicated check; admin-ports must ignore it.
        n = node({"aws_security_group": {"sg": [
            {"ingress": [{"from_port": 22, "to_port": 22, "protocol": "tcp",
                          "cidr_blocks": ["0.0.0.0/0"]}]}]}})
        self.assertEqual(status(aws_security_group_no_public_admin_ports, n), CheckStatus.PASS)

    def test_fail_all_ports(self):
        n = node({"aws_security_group": {"sg": [
            {"ingress": [{"protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}]}]}})
        self.assertEqual(status(aws_security_group_no_public_admin_ports, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_security_group_no_public_admin_ports, EMPTY), CheckStatus.SKIPPED)


class TestRdsEncryption(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_db_instance": {"db": [{"storage_encrypted": True}]}})
        self.assertEqual(status(aws_rds_encryption_at_rest, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_db_instance": {"db": [{"engine": "postgres"}]}})
        self.assertEqual(status(aws_rds_encryption_at_rest, n), CheckStatus.FAIL)

    def test_pass_replica_inherits(self):
        n = node({"aws_db_instance": {"replica": [{"replicate_source_db": "${aws_db_instance.db.identifier}"}]}})
        self.assertEqual(status(aws_rds_encryption_at_rest, n), CheckStatus.PASS)

    def test_pass_module(self):
        n = node_module({"db": [{"source": "terraform-aws-modules/rds/aws", "storage_encrypted": True}]})
        self.assertEqual(status(aws_rds_encryption_at_rest, n), CheckStatus.PASS)

    def test_fail_module(self):
        n = node_module({"db": [{"source": "terraform-aws-modules/rds/aws"}]})
        self.assertEqual(status(aws_rds_encryption_at_rest, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_rds_encryption_at_rest, EMPTY), CheckStatus.SKIPPED)


class TestRdsNotPublic(unittest.TestCase):
    def test_pass_default(self):
        n = node({"aws_db_instance": {"db": [{"engine": "postgres"}]}})
        self.assertEqual(status(aws_rds_not_publicly_accessible, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_db_instance": {"db": [{"publicly_accessible": True}]}})
        self.assertEqual(status(aws_rds_not_publicly_accessible, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_rds_not_publicly_accessible, EMPTY), CheckStatus.SKIPPED)


class TestRdsSnapshotEncryption(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_db_instance": {"db": [{"storage_encrypted": True}]},
                  "aws_db_snapshot": {"s": [{"db_instance_identifier": "${aws_db_instance.db.identifier}"}]}})
        self.assertEqual(status(aws_rds_snapshot_encryption, n), CheckStatus.PASS)

    def test_fail_unencrypted_source(self):
        n = node({"aws_db_instance": {"db": [{"engine": "postgres"}]},
                  "aws_db_snapshot": {"s": [{"db_instance_identifier": "${aws_db_instance.db.identifier}"}]}})
        self.assertEqual(status(aws_rds_snapshot_encryption, n), CheckStatus.FAIL)

    def test_pass_external_source_unresolved(self):
        # Literal external identifier we cannot inspect → no finding.
        n = node({"aws_db_snapshot": {"s": [{"db_instance_identifier": "legacy-db"}]}})
        self.assertEqual(status(aws_rds_snapshot_encryption, n), CheckStatus.PASS)

    def test_skip(self):
        self.assertEqual(status(aws_rds_snapshot_encryption, EMPTY), CheckStatus.SKIPPED)


class TestS3Encryption(unittest.TestCase):
    def test_pass_separate(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_server_side_encryption_configuration": {"e": [
                      {"bucket": "${aws_s3_bucket.b.id}"}]}})
        self.assertEqual(status(aws_s3_encryption_at_rest, n), CheckStatus.PASS)

    def test_pass_inline(self):
        n = node({"aws_s3_bucket": {"b": [{"server_side_encryption_configuration": [{"rule": [{}]}]}]}})
        self.assertEqual(status(aws_s3_encryption_at_rest, n), CheckStatus.PASS)

    def test_fail(self):
        self.assertEqual(status(aws_s3_encryption_at_rest,
                                 node({"aws_s3_bucket": {"b": [{}]}})), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_s3_encryption_at_rest, EMPTY), CheckStatus.SKIPPED)


class TestS3NoStaticWebsite(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(status(aws_s3_no_static_website,
                                 node({"aws_s3_bucket": {"b": [{}]}})), CheckStatus.PASS)

    def test_fail_separate(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_website_configuration": {"w": [{"bucket": "${aws_s3_bucket.b.id}"}]}})
        self.assertEqual(status(aws_s3_no_static_website, n), CheckStatus.FAIL)

    def test_fail_inline(self):
        n = node({"aws_s3_bucket": {"b": [{"website": [{"index_document": "index.html"}]}]}})
        self.assertEqual(status(aws_s3_no_static_website, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_s3_no_static_website, EMPTY), CheckStatus.SKIPPED)


class TestS3NoPublicAcl(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_acl": {"a": [{"bucket": "${aws_s3_bucket.b.id}", "acl": "private"}]}})
        self.assertEqual(status(aws_s3_no_public_acl, n), CheckStatus.PASS)

    def test_fail_canned(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_acl": {"a": [{"acl": "public-read"}]}})
        self.assertEqual(status(aws_s3_no_public_acl, n), CheckStatus.FAIL)

    def test_fail_inline_acl(self):
        n = node({"aws_s3_bucket": {"b": [{"acl": "public-read-write"}]}})
        self.assertEqual(status(aws_s3_no_public_acl, n), CheckStatus.FAIL)

    def test_fail_grant_allusers(self):
        n = node({"aws_s3_bucket": {"b": [{}]},
                  "aws_s3_bucket_acl": {"a": [{"access_control_policy": [
                      {"grant": [{"grantee": [
                          {"uri": "http://acs.amazonaws.com/groups/global/AllUsers", "type": "Group"}]}]}]}]}})
        self.assertEqual(status(aws_s3_no_public_acl, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_s3_no_public_acl, EMPTY), CheckStatus.SKIPPED)


class TestIamPasswordMinLength(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_iam_account_password_policy": {"p": [{"minimum_password_length": 16}]}})
        self.assertEqual(status(aws_iam_password_min_length, n), CheckStatus.PASS)

    def test_fail_too_short(self):
        n = node({"aws_iam_account_password_policy": {"p": [{"minimum_password_length": 8}]}})
        self.assertEqual(status(aws_iam_password_min_length, n), CheckStatus.FAIL)

    def test_fail_absent_is_violation(self):
        # Account-scoped (like guardduty/cloudtrail): no password policy at all
        # is a finding, not a skip — absence IS the violation.
        n = node({"aws_s3_bucket": {"b": [{}]}})
        self.assertEqual(status(aws_iam_password_min_length, n), CheckStatus.FAIL)


class TestIamNoDirectUserPolicies(unittest.TestCase):
    def test_pass_group(self):
        n = node({"aws_iam_user": {"u": [{}]},
                  "aws_iam_group_policy_attachment": {"g": [{}]}})
        self.assertEqual(status(aws_iam_no_direct_user_policies, n), CheckStatus.PASS)

    def test_fail_inline(self):
        n = node({"aws_iam_user_policy": {"up": [{"user": "${aws_iam_user.u.name}"}]}})
        self.assertEqual(status(aws_iam_no_direct_user_policies, n), CheckStatus.FAIL)

    def test_fail_attachment(self):
        n = node({"aws_iam_user_policy_attachment": {"a": [{}]}})
        self.assertEqual(status(aws_iam_no_direct_user_policies, n), CheckStatus.FAIL)

    def test_fail_policy_attachment_with_users(self):
        n = node({"aws_iam_policy_attachment": {"a": [{"users": ["${aws_iam_user.u.name}"]}]}})
        self.assertEqual(status(aws_iam_no_direct_user_policies, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_iam_no_direct_user_policies, EMPTY), CheckStatus.SKIPPED)


class TestAcmDnsValidation(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_acm_certificate": {"c": [{"domain_name": "x.io", "validation_method": "DNS"}]}})
        self.assertEqual(status(aws_acm_cert_dns_validation, n), CheckStatus.PASS)

    def test_fail_email(self):
        n = node({"aws_acm_certificate": {"c": [{"domain_name": "x.io", "validation_method": "EMAIL"}]}})
        self.assertEqual(status(aws_acm_cert_dns_validation, n), CheckStatus.FAIL)

    def test_pass_imported(self):
        n = node({"aws_acm_certificate": {"c": [{"private_key": "x", "certificate_body": "y"}]}})
        self.assertEqual(status(aws_acm_cert_dns_validation, n), CheckStatus.PASS)

    def test_skip(self):
        self.assertEqual(status(aws_acm_cert_dns_validation, EMPTY), CheckStatus.SKIPPED)


class TestEksPrivateEndpoint(unittest.TestCase):
    def test_pass_raw(self):
        n = node({"aws_eks_cluster": {"c": [{"vpc_config": [{"endpoint_private_access": True}]}]}})
        self.assertEqual(status(aws_eks_private_endpoint, n), CheckStatus.PASS)

    def test_fail_raw_default(self):
        n = node({"aws_eks_cluster": {"c": [{"vpc_config": [{"endpoint_public_access": True}]}]}})
        self.assertEqual(status(aws_eks_private_endpoint, n), CheckStatus.FAIL)

    def test_pass_module_default(self):
        # The module defaults cluster_endpoint_private_access to true.
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws"}]})
        self.assertEqual(status(aws_eks_private_endpoint, n), CheckStatus.PASS)

    def test_fail_module_explicit_false(self):
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws",
                                  "cluster_endpoint_private_access": False}]})
        self.assertEqual(status(aws_eks_private_endpoint, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_eks_private_endpoint, EMPTY), CheckStatus.SKIPPED)


class TestDynamoEncryption(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_dynamodb_table": {"t": [{"server_side_encryption": [{"enabled": True}]}]}})
        self.assertEqual(status(aws_dynamodb_encryption, n), CheckStatus.PASS)

    def test_fail_absent_block(self):
        n = node({"aws_dynamodb_table": {"t": [{"name": "items"}]}})
        self.assertEqual(status(aws_dynamodb_encryption, n), CheckStatus.FAIL)

    def test_fail_disabled(self):
        n = node({"aws_dynamodb_table": {"t": [{"server_side_encryption": [{"enabled": False}]}]}})
        self.assertEqual(status(aws_dynamodb_encryption, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_dynamodb_encryption, EMPTY), CheckStatus.SKIPPED)


class TestLambdaNotPublic(unittest.TestCase):
    def test_pass_scoped(self):
        n = node({"aws_lambda_permission": {"p": [
            {"principal": "s3.amazonaws.com", "source_arn": "${aws_s3_bucket.b.arn}"}]}})
        self.assertEqual(status(aws_lambda_not_public, n), CheckStatus.PASS)

    def test_pass_star_with_source(self):
        n = node({"aws_lambda_permission": {"p": [{"principal": "*", "source_account": "123456789012"}]}})
        self.assertEqual(status(aws_lambda_not_public, n), CheckStatus.PASS)

    def test_pass_star_with_org_id(self):
        # principal "*" scoped to an AWS Organization is org-internal, not public.
        n = node({"aws_lambda_permission": {"p": [{"principal": "*", "principal_org_id": "o-abc123"}]}})
        self.assertEqual(status(aws_lambda_not_public, n), CheckStatus.PASS)

    def test_fail_star(self):
        n = node({"aws_lambda_permission": {"p": [{"principal": "*"}]}})
        self.assertEqual(status(aws_lambda_not_public, n), CheckStatus.FAIL)

    def test_fail_url_none(self):
        n = node({"aws_lambda_function_url": {"u": [{"authorization_type": "NONE"}]}})
        self.assertEqual(status(aws_lambda_not_public, n), CheckStatus.FAIL)

    def test_skip(self):
        self.assertEqual(status(aws_lambda_not_public, EMPTY), CheckStatus.SKIPPED)


class TestCloudTrailLogFileValidation(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_cloudtrail": {"t": [{"enable_log_file_validation": True}]}})
        self.assertEqual(status(aws_cloudtrail_log_file_validation, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_cloudtrail": {"t": [{"name": "main"}]}})
        self.assertEqual(status(aws_cloudtrail_log_file_validation, n), CheckStatus.FAIL)

    def test_skip_no_trail(self):
        # Trail absence is owned by aws-cloudtrail-multi-region.
        n = node({"aws_s3_bucket": {"b": [{}]}})
        self.assertEqual(status(aws_cloudtrail_log_file_validation, n), CheckStatus.SKIPPED)


class TestCloudTrailKmsEncryption(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_cloudtrail": {"t": [{"kms_key_id": "${aws_kms_key.ct.arn}"}]}})
        self.assertEqual(status(aws_cloudtrail_kms_encryption, n), CheckStatus.PASS)

    def test_fail(self):
        n = node({"aws_cloudtrail": {"t": [{"name": "main"}]}})
        self.assertEqual(status(aws_cloudtrail_kms_encryption, n), CheckStatus.FAIL)

    def test_skip_no_trail(self):
        n = node({"aws_s3_bucket": {"b": [{}]}})
        self.assertEqual(status(aws_cloudtrail_kms_encryption, n), CheckStatus.SKIPPED)



class TestIamRolePermissionsBoundary(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_iam_role": {"app": [
            {"permissions_boundary": "arn:aws:iam::1:policy/boundary"}]}})
        self.assertEqual(
            status(aws_iam_role_permissions_boundary, n), CheckStatus.PASS)

    def test_fail_absent(self):
        n = node({"aws_iam_role": {"app": [{"name": "app"}]}})
        self.assertEqual(
            status(aws_iam_role_permissions_boundary, n), CheckStatus.FAIL)

    def test_fail_empty_string(self):
        # An empty boundary is as unbounded as no boundary.
        n = node({"aws_iam_role": {"app": [{"permissions_boundary": "  "}]}})
        self.assertEqual(
            status(aws_iam_role_permissions_boundary, n), CheckStatus.FAIL)

    def test_skip_no_roles(self):
        n = node({"aws_s3_bucket": {"b": [{}]}})
        self.assertEqual(
            status(aws_iam_role_permissions_boundary, n), CheckStatus.SKIPPED)

    def test_skip_no_terraform(self):
        self.assertEqual(
            status(aws_iam_role_permissions_boundary, EMPTY), CheckStatus.SKIPPED)


class TestImdsv2Required(unittest.TestCase):
    def test_pass(self):
        n = node({"aws_launch_template": {"lt": [{"metadata_options": [
            {"http_tokens": "required", "http_put_response_hop_limit": 1}]}]}})
        self.assertEqual(status(aws_imdsv2_required, n), CheckStatus.PASS)

    def test_pass_string_hop_limit(self):
        # hcl2json renders numbers as strings in some shapes.
        n = node({"aws_instance": {"i": [{"metadata_options": [
            {"http_tokens": "required", "http_put_response_hop_limit": "1"}]}]}})
        self.assertEqual(status(aws_imdsv2_required, n), CheckStatus.PASS)

    def test_fail_optional_tokens(self):
        n = node({"aws_instance": {"i": [{"metadata_options": [
            {"http_tokens": "optional", "http_put_response_hop_limit": 1}]}]}})
        self.assertEqual(status(aws_imdsv2_required, n), CheckStatus.FAIL)

    def test_fail_hop_limit_two(self):
        # The AWS default. A pod on the host can reach the node role at 2.
        n = node({"aws_launch_template": {"lt": [{"metadata_options": [
            {"http_tokens": "required", "http_put_response_hop_limit": 2}]}]}})
        self.assertEqual(status(aws_imdsv2_required, n), CheckStatus.FAIL)

    def test_pass_hop_limit_unset(self):
        # The provider default is 1, which is already safe — requiring it to be
        # written out would fail a hardened config on a wrong premise.
        n = node({"aws_instance": {"i": [{"metadata_options": [
            {"http_tokens": "required"}]}]}})
        self.assertEqual(status(aws_imdsv2_required, n), CheckStatus.PASS)

    def test_fail_no_metadata_options(self):
        # http_tokens defaults to "optional", so absence leaves IMDSv1 open.
        n = node({"aws_instance": {"i": [{"ami": "ami-1"}]}})
        self.assertEqual(status(aws_imdsv2_required, n), CheckStatus.FAIL)

    def test_fail_hop_limit_unresolved(self):
        # Set but not a literal — unknown is not the same as unset.
        n = node({"aws_instance": {"i": [{"metadata_options": [
            {"http_tokens": "required",
             "http_put_response_hop_limit": "${var.hops}"}]}]}})
        self.assertEqual(status(aws_imdsv2_required, n), CheckStatus.FAIL)

    def test_skip_no_instances(self):
        n = node({"aws_s3_bucket": {"b": [{}]}})
        self.assertEqual(status(aws_imdsv2_required, n), CheckStatus.SKIPPED)


class TestOpenTofuStateEncryption(unittest.TestCase):
    def test_pass(self):
        n = node_terraform([{"encryption": [{
            "key_provider": [{"aws_kms": [{"key": [{"kms_key_id": "k"}]}]}],
            "state": [{"method": "${method.aes_gcm.m}", "enforced": True}],
        }]}])
        self.assertEqual(status(opentofu_state_encryption, n), CheckStatus.PASS)

    def test_fail_no_encryption_block(self):
        n = node_terraform([{"required_version": ">= 1.6"}])
        self.assertEqual(status(opentofu_state_encryption, n), CheckStatus.FAIL)

    def test_fail_not_enforced(self):
        # Without enforced it falls back to plaintext instead of failing.
        n = node_terraform([{"encryption": [{
            "key_provider": [{"aws_kms": [{"key": [{}]}]}],
            "state": [{"method": "${method.aes_gcm.m}", "enforced": False}],
        }]}])
        self.assertEqual(status(opentofu_state_encryption, n), CheckStatus.FAIL)

    def test_fail_no_key_provider(self):
        n = node_terraform([{"encryption": [{
            "state": [{"method": "${method.aes_gcm.m}", "enforced": True}]}]}])
        self.assertEqual(status(opentofu_state_encryption, n), CheckStatus.FAIL)

    def test_skip_no_terraform(self):
        self.assertEqual(
            status(opentofu_state_encryption, EMPTY), CheckStatus.SKIPPED)


class TlsPolicyApprovedTest(unittest.TestCase):
    """aws-tls-policy-approved: the negotiated suite, not just that TLS is on."""

    APPROVED = "ELBSecurityPolicy-TLS13-1-2-2021-06,TLSv1.2_2021"

    def run_with(self, n, approved=None):
        val = self.APPROVED if approved is None else approved
        os.environ["LUNAR_VAR_approved_tls_policies"] = val
        try:
            return status(aws_tls_policy_approved, n)
        finally:
            os.environ.pop("LUNAR_VAR_approved_tls_policies", None)

    def listener(self, **kw):
        cfg = {"protocol": "HTTPS"}
        cfg.update(kw)
        return node({"aws_lb_listener": {"web": [cfg]}})

    def test_approved_ssl_policy_passes(self):
        self.assertEqual(
            self.run_with(self.listener(ssl_policy="ELBSecurityPolicy-TLS13-1-2-2021-06")),
            CheckStatus.PASS)

    def test_unapproved_ssl_policy_fails(self):
        self.assertEqual(
            self.run_with(self.listener(ssl_policy="ELBSecurityPolicy-TLS-1-0-2015-04")),
            CheckStatus.FAIL)

    def test_https_listener_with_no_ssl_policy_fails(self):
        self.assertEqual(self.run_with(self.listener()), CheckStatus.FAIL)

    def test_missing_ssl_policy_says_so_rather_than_naming_a_bogus_policy(self):
        # Without its own branch this still fails, but reports `uses None` and
        # sends the reader looking for a policy called "None".
        msg = failure_message(aws_tls_policy_approved, self.listener(),
                              approved_tls_policies=self.APPROVED)
        self.assertIn("sets no ssl_policy", msg)
        self.assertNotIn("uses None", msg)

    def test_plaintext_listener_is_not_this_checks_business(self):
        n = node({"aws_lb_listener": {"web": [{"protocol": "HTTP"}]}})
        self.assertEqual(self.run_with(n), CheckStatus.SKIPPED)

    def test_skips_when_no_approved_list_configured(self):
        n = self.listener(ssl_policy="ELBSecurityPolicy-TLS-1-0-2015-04")
        self.assertEqual(self.run_with(n, approved=""), CheckStatus.SKIPPED)

    def test_cloudfront_minimum_protocol_version(self):
        bad = node({"aws_cloudfront_distribution": {"cdn": [
            {"viewer_certificate": [{"minimum_protocol_version": "TLSv1"}]}]}})
        good = node({"aws_cloudfront_distribution": {"cdn": [
            {"viewer_certificate": [{"minimum_protocol_version": "TLSv1.2_2021"}]}]}})
        self.assertEqual(self.run_with(bad), CheckStatus.FAIL)
        self.assertEqual(self.run_with(good), CheckStatus.PASS)

    def test_cloudfront_default_certificate_pins_its_own_policy(self):
        n = node({"aws_cloudfront_distribution": {"cdn": [
            {"viewer_certificate": [{"cloudfront_default_certificate": True}]}]}})
        self.assertEqual(self.run_with(n), CheckStatus.SKIPPED)

    def test_explicit_false_default_certificate_is_still_checked(self):
        # The provider only accepts minimum_protocol_version when this is false,
        # so `= false` is the normal ACM shape. Skipping on presence let a weak
        # minimum_protocol_version through unchecked.
        n = node({"aws_cloudfront_distribution": {"cdn": [{"viewer_certificate": [{
            "cloudfront_default_certificate": False,
            "minimum_protocol_version": "TLSv1",
        }]}]}})
        self.assertEqual(self.run_with(n), CheckStatus.FAIL)

    def test_api_gateway_security_policy(self):
        bad = node({"aws_api_gateway_domain_name": {"api": [
            {"security_policy": "TLS_1_0"}]}})
        self.assertEqual(self.run_with(bad), CheckStatus.FAIL)

    def test_skips_with_no_terraform_data(self):
        self.assertEqual(self.run_with(EMPTY), CheckStatus.SKIPPED)


class StatefulBackupConfiguredTest(unittest.TestCase):
    """aws-stateful-backup-configured: MC 9 backup coverage."""

    def test_rds_with_retention_passes(self):
        n = node({"aws_db_instance": {"db": [{"backup_retention_period": 7}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.PASS)

    def test_rds_with_zero_retention_fails(self):
        n = node({"aws_db_instance": {"db": [{"backup_retention_period": 0}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.FAIL)

    def test_rds_with_undeclared_retention_fails(self):
        n = node({"aws_db_instance": {"db": [{"engine": "postgres"}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.FAIL)

    def test_undeclared_retention_is_not_reported_as_unparseable(self):
        # as_int(None) is None, so without its own branch this fails with "not a
        # literal value" — which points at interpolation rather than absence.
        n = node({"aws_db_instance": {"db": [{"engine": "postgres"}]}})
        msg = failure_message(aws_stateful_backup_configured, n)
        self.assertIn("does not declare backup_retention_period", msg)
        self.assertNotIn("not a literal value", msg)

    def test_rds_with_unresolved_retention_fails(self):
        # Unknown is not known-good.
        n = node({"aws_db_instance": {"db": [
            {"backup_retention_period": "${var.retention}"}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.FAIL)

    def test_read_replica_is_skipped(self):
        n = node({"aws_db_instance": {"replica": [
            {"replicate_source_db": "primary"}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.SKIPPED)

    def test_dynamodb_pitr_enabled_passes(self):
        n = node({"aws_dynamodb_table": {"t": [
            {"point_in_time_recovery": [{"enabled": True}]}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.PASS)

    def test_dynamodb_pitr_disabled_fails(self):
        n = node({"aws_dynamodb_table": {"t": [
            {"point_in_time_recovery": [{"enabled": False}]}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.FAIL)

    def test_dynamodb_without_pitr_block_fails(self):
        n = node({"aws_dynamodb_table": {"t": [{"name": "t"}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.FAIL)

    # EFS backups are a separate aws_efs_backup_policy resource keyed by
    # file_system_id. The first cut asserted an inline backup_policy block that
    # the provider has no such argument for, so the check could never pass on
    # real configuration and the test only went green on an invented shape.
    def test_efs_with_enabled_backup_policy_resource_passes(self):
        n = node({
            "aws_efs_file_system": {"fs": [{"encrypted": True}]},
            "aws_efs_backup_policy": {"fs": [{
                "file_system_id": "${aws_efs_file_system.fs.id}",
                "backup_policy": [{"status": "ENABLED"}],
            }]},
        })
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.PASS)

    def test_efs_with_disabled_backup_policy_resource_fails(self):
        n = node({
            "aws_efs_file_system": {"fs": [{"encrypted": True}]},
            "aws_efs_backup_policy": {"fs": [{
                "file_system_id": "${aws_efs_file_system.fs.id}",
                "backup_policy": [{"status": "DISABLED"}],
            }]},
        })
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.FAIL)

    def test_efs_with_no_backup_policy_resource_fails(self):
        n = node({"aws_efs_file_system": {"fs": [{"encrypted": True}]}})
        msg = failure_message(aws_stateful_backup_configured, n)
        self.assertIn("has no aws_efs_backup_policy", msg)

    def test_efs_backup_policy_for_a_different_filesystem_does_not_count(self):
        # Correlation must be by file_system_id, not "some backup policy exists".
        n = node({
            "aws_efs_file_system": {"unbacked": [{"encrypted": True}]},
            "aws_efs_backup_policy": {"other": [{
                "file_system_id": "${aws_efs_file_system.somethingelse.id}",
                "backup_policy": [{"status": "ENABLED"}],
            }]},
        })
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.FAIL)

    def test_skips_when_no_stateful_resources(self):
        n = node({"aws_lb": {"lb": [{"internal": True}]}})
        self.assertEqual(status(aws_stateful_backup_configured, n), CheckStatus.SKIPPED)

    def test_skips_with_no_terraform_data(self):
        self.assertEqual(status(aws_stateful_backup_configured, EMPTY), CheckStatus.SKIPPED)


class TestEksModuleV21Arguments(unittest.TestCase):
    """terraform-aws-modules/eks v21 dropped the cluster_ prefix from these arguments."""

    def test_logging_pass_v21_name(self):
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws", "version": "21.24.2",
                                  "enabled_log_types": ["api", "audit", "authenticator", "controllerManager", "scheduler"]}]})
        self.assertEqual(status(aws_eks_control_plane_logging, n), CheckStatus.PASS)

    def test_logging_fail_v21_name_partial(self):
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws",
                                  "enabled_log_types": ["api"]}]})
        self.assertEqual(status(aws_eks_control_plane_logging, n), CheckStatus.FAIL)
        # The configured list is read, not the module default (which has audit).
        self.assertIn("audit, authenticator", failure_message(aws_eks_control_plane_logging, n))

    def test_private_endpoint_fail_v21_false(self):
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws",
                                  "endpoint_private_access": False}]})
        self.assertEqual(status(aws_eks_private_endpoint, n), CheckStatus.FAIL)
        self.assertIn("sets endpoint_private_access = false",
                      failure_message(aws_eks_private_endpoint, n))

    def test_private_endpoint_pass_v21_true_with_public(self):
        # A public endpoint is not this check's concern.
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws",
                                  "endpoint_private_access": True, "endpoint_public_access": True}]})
        self.assertEqual(status(aws_eks_private_endpoint, n), CheckStatus.PASS)

    def test_private_endpoint_fail_v20_false_message(self):
        n = node_module({"eks": [{"source": "terraform-aws-modules/eks/aws",
                                  "cluster_endpoint_private_access": "false"}]})
        self.assertIn("sets cluster_endpoint_private_access = false",
                      failure_message(aws_eks_private_endpoint, n))


class TestModuleSourceMatching(unittest.TestCase):
    """Module calls match the registry path by whole segment; submodules only on request."""

    def test_matches(self):
        for src in ("terraform-aws-modules/eks/aws",
                    "registry.terraform.io/terraform-aws-modules/eks/aws",
                    "terraform-aws-modules/eks/aws?ref=v21.0.0",
                    "Terraform-AWS-Modules/EKS/aws"):
            self.assertTrue(module_source_matches(src, "terraform-aws-modules/eks/aws"), src)

    def test_no_match(self):
        for src in ("terraform-aws-modules/eks-pod-identity/aws",
                    "terraform-aws-modules/eks/aws//modules/karpenter",
                    "terraform-aws-modules/eks/aws//modules/eks-managed-node-group?ref=v21.0.0",
                    "terraform-aws-modules/eks",
                    "./modules/eks"):
            self.assertFalse(module_source_matches(src, "terraform-aws-modules/eks/aws"), src)

    def test_submodule_on_request(self):
        want = "terraform-aws-modules/rds/aws//modules/db_instance"
        self.assertTrue(module_source_matches("terraform-aws-modules/rds/aws//modules/db_instance", want))
        self.assertFalse(module_source_matches("terraform-aws-modules/rds/aws", want))
        self.assertFalse(module_source_matches("terraform-aws-modules/rds/aws//modules/db_subnet_group", want))

    def test_git_subdir_not_confused_with_scheme(self):
        self.assertFalse(module_source_matches(
            "git::https://example.com/terraform-aws-modules/vpc/aws//modules/vpc-endpoints?ref=v6",
            "terraform-aws-modules/vpc/aws"))

    def test_eks_ignores_sibling_and_submodules(self):
        # One real cluster plus the karpenter submodule and eks-pod-identity:
        # only the cluster is evaluated.
        n = node_module({
            "eks": [{"source": "terraform-aws-modules/eks/aws", "enabled_log_types": ["api", "audit", "authenticator", "controllerManager", "scheduler"]}],
            "karpenter": [{"source": "terraform-aws-modules/eks/aws//modules/karpenter"}],
            "pod_identity": [{"source": "terraform-aws-modules/eks-pod-identity/aws"}],
        })
        self.assertEqual(status(aws_eks_control_plane_logging, n), CheckStatus.PASS)

    def test_eks_skip_when_only_non_cluster_modules(self):
        n = node_module({
            "karpenter": [{"source": "terraform-aws-modules/eks/aws//modules/karpenter"}],
            "pod_identity": [{"source": "terraform-aws-modules/eks-pod-identity/aws"}],
        })
        self.assertEqual(status(aws_eks_control_plane_logging, n), CheckStatus.SKIPPED)
        self.assertEqual(status(aws_eks_private_endpoint, n), CheckStatus.SKIPPED)

    def test_vpc_skip_vpc_endpoints_submodule(self):
        n = node_module({"endpoints": [{"source": "terraform-aws-modules/vpc/aws//modules/vpc-endpoints"}]})
        self.assertEqual(status(aws_vpc_flow_logs, n), CheckStatus.SKIPPED)

    def test_rds_skip_parameter_group_submodule(self):
        n = node_module({"pg": [{"source": "terraform-aws-modules/rds/aws//modules/db_parameter_group"}]})
        self.assertEqual(status(aws_rds_cloudwatch_logging, n), CheckStatus.SKIPPED)

    def test_rds_db_instance_submodule_and_aurora_still_evaluated(self):
        for src in ("terraform-aws-modules/rds/aws//modules/db_instance",
                    "terraform-aws-modules/rds-aurora/aws"):
            n = node_module({"db": [{"source": src}]})
            self.assertEqual(status(aws_rds_cloudwatch_logging, n), CheckStatus.FAIL, src)


class TestElbNetworkLoadBalancers(unittest.TestCase):
    """Only plaintext HTTP is flagged; NLB/GWLB access logs are out of scope."""

    def test_https_only_skip_tcp_only(self):
        n = node({"aws_lb_listener": {"tcp": [{"protocol": "TCP"}], "udp": [{"protocol": "UDP"}],
                                      "both": [{"protocol": "TCP_UDP"}]}})
        self.assertEqual(status(aws_elb_https_only, n), CheckStatus.SKIPPED)

    def test_https_only_pass_tcp_alongside_https(self):
        n = node({"aws_lb_listener": {"tcp": [{"protocol": "TCP"}], "web": [{"protocol": "HTTPS"}]}})
        self.assertEqual(status(aws_elb_https_only, n), CheckStatus.PASS)

    def test_https_only_pass_nlb_tls(self):
        n = node({"aws_lb_listener": {"tls": [{"protocol": "TLS"}]}})
        self.assertEqual(status(aws_elb_https_only, n), CheckStatus.PASS)

    def test_https_only_fail_names_only_http(self):
        n = node({"aws_lb_listener": {"tcp": [{"protocol": "TCP"}], "web": [{"protocol": "HTTP"}]}})
        self.assertEqual(status(aws_elb_https_only, n), CheckStatus.FAIL)
        msg = failure_message(aws_elb_https_only, n)
        self.assertIn("aws_lb_listener.web", msg)
        self.assertNotIn("aws_lb_listener.tcp", msg)

    def test_https_only_fail_default_protocol_is_http(self):
        n = node({"aws_lb_listener": {"web": [{"port": 80}]}})
        self.assertEqual(status(aws_elb_https_only, n), CheckStatus.FAIL)

    def test_https_only_fail_classic_tcp(self):
        # Classic listeners stay strict: Security Hub ELB.3 flags TCP too.
        n = node({"aws_elb": {"c": [{"listener": [{"lb_protocol": "TCP"}]}]}})
        self.assertEqual(status(aws_elb_https_only, n), CheckStatus.FAIL)

    def test_access_logging_skip_nlb_and_gwlb(self):
        n = node({"aws_lb": {"nlb": [{"load_balancer_type": "network"}],
                             "gwlb": [{"load_balancer_type": "gateway"}]}})
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.SKIPPED)

    def test_access_logging_nlb_ignored_alb_checked(self):
        n = node({"aws_lb": {"nlb": [{"load_balancer_type": "network"}],
                             "alb": [{"load_balancer_type": "application"}]}})
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.FAIL)
        msg = failure_message(aws_elb_access_logging, n)
        self.assertIn("aws_lb.alb", msg)
        self.assertNotIn("aws_lb.nlb", msg)

    def test_access_logging_classic_still_checked(self):
        n = node({"aws_elb": {"c": [{}]}})
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.FAIL)



def node_files(*files):
    """Build a node from (path, hcl) pairs."""
    return Node.from_component_json(
        {"iac": {"native": {"terraform": {"files": [
            {"path": path, "hcl": hcl} for path, hcl in files
        ]}}}}
    )


LBC = "alb.ingress.kubernetes.io/"


def ingress(annotations=None, ingress_class="alb"):
    """A kubernetes_ingress_v1 body as hcl2json renders it."""
    cfg = {"metadata": [{"name": "x"}], "spec": [{"rule": [{}]}]}
    if annotations is not None:
        cfg["metadata"][0]["annotations"] = annotations
    if ingress_class is not None:
        cfg["spec"][0]["ingress_class_name"] = ingress_class
    return [cfg]


PUBLIC = {LBC + "group.name": "web", LBC + "scheme": "internet-facing",
          LBC + "load-balancer-attributes": "idle_timeout.timeout_seconds=600"}
INTERNAL = {LBC + "group.name": "web-internal", LBC + "scheme": "internal",
            LBC + "load-balancer-attributes": "idle_timeout.timeout_seconds=600"}

# The annotations expression hcl2json emits for merge(local.<name>, {...}),
# comments and an unquoted value included.
MERGED = ('${merge(local.%s, {\n      "' + LBC + 'group.order" = "10"\n'
          '      # a comment with "quotes" and = signs\n'
          '      "' + LBC + 'inbound-cidrs" = var.vpc_cidr_block # trailing comment\n'
          '      "' + LBC + 'backend-protocol-version" = "GRPC"\n    })}')


class TestLoadBalancerControllerAlbs(unittest.TestCase):
    """ALBs the AWS Load Balancer Controller builds from Terraform-declared Ingresses."""

    def test_waf_fail_names_group_and_members(self):
        n = node({"kubernetes_ingress_v1": {"api": ingress(PUBLIC), "ui": ingress(PUBLIC)}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.FAIL)
        self.assertIn('ALB group "web" (kubernetes_ingress_v1.api, kubernetes_ingress_v1.ui)',
                      failure_message(aws_alb_waf_enabled, n))

    def test_waf_pass_when_one_group_member_sets_acl(self):
        waf = dict(PUBLIC, **{LBC + "wafv2-acl-arn": "${aws_wafv2_web_acl.main.arn}"})
        n = node({"kubernetes_ingress_v1": {"api": ingress(PUBLIC), "ui": ingress(waf)}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.PASS)

    def test_waf_pass_legacy_acl_id(self):
        waf = dict(PUBLIC, **{LBC + "waf-acl-id": "abc-123"})
        n = node({"kubernetes_ingress": {"api": ingress(waf)}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.PASS)

    def test_waf_empty_acl_is_no_waf(self):
        waf = dict(PUBLIC, **{LBC + "wafv2-acl-arn": ""})
        n = node({"kubernetes_ingress_v1": {"api": ingress(waf)}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.FAIL)

    def test_waf_skip_internal_and_default_scheme(self):
        no_scheme = {LBC + "group.name": "g"}
        n = node({"kubernetes_ingress_v1": {"a": ingress(INTERNAL), "b": ingress(no_scheme)}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.SKIPPED)

    def test_waf_fail_names_only_internet_facing_group(self):
        n = node({"kubernetes_ingress_v1": {"pub": ingress(PUBLIC), "priv": ingress(INTERNAL)}})
        msg = failure_message(aws_alb_waf_enabled, n)
        self.assertIn('ALB group "web" (kubernetes_ingress_v1.pub)', msg)
        self.assertNotIn("web-internal", msg)

    def test_ungrouped_ingress_is_its_own_alb(self):
        n = node({"kubernetes_ingress_v1": {"solo": ingress({LBC + "scheme": "internet-facing"})}})
        self.assertIn("ALB for kubernetes_ingress_v1.solo", failure_message(aws_alb_waf_enabled, n))

    def test_class_annotation_or_alb_annotation_counts_as_controller(self):
        n = node({"kubernetes_ingress_v1": {
            "a": ingress({"kubernetes.io/ingress.class": "alb"}, ingress_class=None),
            "b": ingress({LBC + "scheme": "internet-facing"}, ingress_class=None)}})
        self.assertIn("ALB for kubernetes_ingress_v1.a", failure_message(aws_elb_access_logging, n))
        self.assertIn("ALB for kubernetes_ingress_v1.b", failure_message(aws_alb_waf_enabled, n))

    def test_other_ingress_controllers_ignored(self):
        n = node({"kubernetes_ingress_v1": {"a": ingress({"nginx.ingress.kubernetes.io/ssl-redirect": "true"},
                                                          ingress_class="nginx")}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.SKIPPED)
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.SKIPPED)

    def test_merge_with_local_resolved(self):
        n = node_files(("app/locals.tf", {"locals": [{"common": PUBLIC}]}),
                       ("app/ingress.tf", {"resource": {"kubernetes_ingress_v1": {
                           "api": ingress(MERGED % "common")}}}))
        self.assertIn('ALB group "web" (kubernetes_ingress_v1.api)', failure_message(aws_alb_waf_enabled, n))
        self.assertIn('ALB group "web" (kubernetes_ingress_v1.api)', failure_message(aws_elb_access_logging, n))

    def test_merge_inline_pair_overrides_local(self):
        # The key right after an unquoted value with a trailing comment.
        logs = MERGED.replace('# trailing comment\n', '# trailing comment\n "' + LBC +
                              'load-balancer-attributes" = "access_logs.s3.enabled=true,access_logs.s3.bucket=logs"\n')
        n = node_files(("locals.tf", {"locals": [{"common": INTERNAL}]}),
                       ("ingress.tf", {"resource": {"kubernetes_ingress_v1": {"api": ingress(logs % "common")}}}))
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.PASS)

    def test_local_from_another_directory_not_used(self):
        n = node_files(("other/locals.tf", {"locals": [{"common": PUBLIC}]}),
                       ("app/ingress.tf", {"resource": {"kubernetes_ingress_v1": {
                           "api": ingress(MERGED % "common")}}}))
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.SKIPPED)
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.PASS)

    def test_access_logs_attribute_present(self):
        on = dict(INTERNAL, **{LBC + "load-balancer-attributes":
                               "idle_timeout.timeout_seconds=600, Access_Logs.S3.Enabled=TRUE,access_logs.s3.bucket=logs"})
        n = node({"kubernetes_ingress_v1": {"a": ingress(INTERNAL), "b": ingress(on)}})
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.PASS)

    def test_access_logs_attribute_absent_or_disabled(self):
        off = dict(PUBLIC, **{LBC + "load-balancer-attributes": "access_logs.s3.enabled=false"})
        n = node({"kubernetes_ingress_v1": {"a": ingress(off), "b": ingress(INTERNAL)}})
        msg = failure_message(aws_elb_access_logging, n)
        self.assertIn('ALB group "web" (kubernetes_ingress_v1.a)', msg)
        self.assertIn('ALB group "web-internal" (kubernetes_ingress_v1.b)', msg)

    def test_unknown_expressions_never_fail(self):
        unknown_attrs = dict(INTERNAL, **{LBC + "load-balancer-attributes": "${var.lb_attributes}"})
        unknown_group = dict(PUBLIC, **{LBC + "group.name": "${var.group}"})
        n = node_files(("locals.tf", {"locals": [{"common": PUBLIC}]}),
                       ("ingress.tf", {"resource": {"kubernetes_ingress_v1": {
                           "whole": ingress("${var.annotations}"),
                           "merged": ingress("${merge(local.common, var.extra)}"),
                           "missing_local": ingress("${merge(local.nope, {})}"),
                           "malformed": ingress("${merge(var.x})}"),
                           "attrs": ingress(unknown_attrs),
                       }, "kubernetes_ingress": {"group": ingress(unknown_group)}}}))
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.PASS)
        self.assertEqual(status(aws_elb_access_logging, n), CheckStatus.PASS)

    def test_waf_association_on_looked_up_alb_not_failed(self):
        n = node({"kubernetes_ingress_v1": {"api": ingress(PUBLIC)},
                  "aws_wafv2_web_acl_association": {"a": [{"resource_arn": "${data.aws_lb.ingress.arn}"}]}})
        self.assertEqual(status(aws_alb_waf_enabled, n), CheckStatus.PASS)


class TestEbsImplicitRootVolumes(unittest.TestCase):
    """Root volumes left to the AMI default: instances and EKS-module node groups."""

    EKS = "terraform-aws-modules/eks/aws"
    ENCRYPTED = {"xvda": {"device_name": "/dev/xvda", "ebs": {"volume_size": 50, "encrypted": True}}}

    def eks(self, **args):
        return dict({"source": self.EKS, "version": "21.24.2"}, **args)

    def test_instance_without_root_block_device_fails(self):
        n = node({"aws_instance": {"bastion": [{"instance_type": "t4g.nano"}]}})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.FAIL)
        self.assertIn("aws_instance.bastion root volume", failure_message(aws_ebs_volume_encryption, n))

    def test_instance_without_root_block_device_passes_with_account_default(self):
        n = node({"aws_instance": {"bastion": [{"instance_type": "t4g.nano"}]},
                  "aws_ebs_encryption_by_default": {"this": [{}]}})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.PASS)

    def test_account_default_disabled_does_not_count(self):
        n = node({"aws_instance": {"bastion": [{}]},
                  "aws_ebs_encryption_by_default": {"this": [{"enabled": False}]}})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.FAIL)

    def test_account_default_keeps_explicit_offenders_and_names_covered(self):
        n = node({"aws_instance": {"bastion": [{}]}, "aws_ebs_volume": {"data": [{}]},
                  "aws_ebs_encryption_by_default": {"this": [{"enabled": True}]}})
        msg = failure_message(aws_ebs_volume_encryption, n)
        self.assertIn("aws_ebs_volume.data", msg)
        self.assertIn("aws_instance.bastion root volume (no root_block_device) covered by "
                      "aws_ebs_encryption_by_default", msg)

    def test_instance_from_launch_template_not_flagged(self):
        n = node({"aws_instance": {"web": [{"launch_template": [{"id": "${aws_launch_template.web.id}"}]}]}})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.PASS)

    def test_node_groups_without_mappings_fail(self):
        n = node_module({"eks": [self.eks(eks_managed_node_groups={
            "system": {"instance_types": ["m6i.large"], "disk_size": 50},
            "services": {"instance_types": ["m6i.large"], "block_device_mappings": self.ENCRYPTED},
        })]})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.FAIL)
        msg = failure_message(aws_ebs_volume_encryption, n)
        self.assertIn("module.eks.eks_managed_node_groups.system", msg)
        self.assertNotIn("services", msg)

    def test_node_groups_with_encrypted_mappings_pass(self):
        n = node_module({"eks": [self.eks(
            eks_managed_node_groups={"system": {"block_device_mappings": self.ENCRYPTED}},
            self_managed_node_groups={"batch": {"block_device_mappings": self.ENCRYPTED}})]})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.PASS)

    def test_mapping_without_encrypted_fails(self):
        plain = {"xvda": {"device_name": "/dev/xvda", "ebs": {"volume_size": 50}}}
        n = node_module({"eks": [self.eks(self_managed_node_groups={"batch": {"block_device_mappings": plain}})]})
        self.assertIn("module.eks.self_managed_node_groups.batch", failure_message(aws_ebs_volume_encryption, n))

    def test_node_groups_pass_with_account_default(self):
        n = node_files(("eks.tf", {"module": {"eks": [self.eks(eks_managed_node_groups={"system": {}})]}}),
                       ("ebs.tf", {"resource": {"aws_ebs_encryption_by_default": {"this": [{"enabled": True}]}}}))
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.PASS)

    def test_v20_defaults_block(self):
        defaults = {"block_device_mappings": self.ENCRYPTED}
        n = node_module({"eks": [self.eks(eks_managed_node_group_defaults=defaults,
                                          eks_managed_node_groups={"system": {}})]})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.PASS)
        plain = {"xvda": {"ebs": {"encrypted": False}}}
        n = node_module({"eks": [self.eks(eks_managed_node_group_defaults=defaults,
                                          eks_managed_node_groups={"gpu": {"block_device_mappings": plain}})]})
        self.assertIn("module.eks.eks_managed_node_groups.gpu", failure_message(aws_ebs_volume_encryption, n))

    def test_standalone_node_group_submodule(self):
        src = self.EKS + "//modules/eks-managed-node-group"
        n = node_module({"ng": [{"source": src, "block_device_mappings": self.ENCRYPTED}]})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.PASS)
        n = node_module({"ng": [{"source": src}]})
        self.assertIn("module.ng", failure_message(aws_ebs_volume_encryption, n))

    def test_launch_template_choice(self):
        # EKS's default launch template ignores block_device_mappings; an existing
        # launch template (launch_template_id) decides for itself.
        n = node_module({"eks": [self.eks(eks_managed_node_groups={
            "default_lt": {"use_custom_launch_template": False, "block_device_mappings": self.ENCRYPTED},
            "own_lt": {"create_launch_template": False, "launch_template_id": "${aws_launch_template.x.id}"},
        })]})
        msg = failure_message(aws_ebs_volume_encryption, n)
        self.assertIn("module.eks.eks_managed_node_groups.default_lt", msg)
        self.assertNotIn("own_lt", msg)

    def test_unevaluable_node_groups_not_flagged(self):
        n = node_module({"eks": [self.eks(eks_managed_node_groups="${var.node_groups}")]})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.SKIPPED)
        n = node_module({"eks": [self.eks(eks_managed_node_groups={
            "a": "${var.group_a}",
            "b": {"block_device_mappings": "${local.mappings}"},
            "c": {"block_device_mappings": {"xvda": {"ebs": {"encrypted": "${var.encrypt}"}}}},
            "d": {"use_custom_launch_template": "${var.custom}"},
        })]})
        self.assertEqual(status(aws_ebs_volume_encryption, n), CheckStatus.SKIPPED)


if __name__ == "__main__":
    unittest.main()
