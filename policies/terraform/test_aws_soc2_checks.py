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
        n = node_module({"db": [{"source": "terraform-aws-modules/rds",
                                 "enabled_cloudwatch_logs_exports": ["postgresql"]}]})
        self.assertEqual(status(aws_rds_cloudwatch_logging, n), CheckStatus.PASS)

    def test_fail_module(self):
        n = node_module({"db": [{"source": "terraform-aws-modules/rds"}]})
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
        n = node_module({"db": [{"source": "terraform-aws-modules/rds", "storage_encrypted": True}]})
        self.assertEqual(status(aws_rds_encryption_at_rest, n), CheckStatus.PASS)

    def test_fail_module(self):
        n = node_module({"db": [{"source": "terraform-aws-modules/rds"}]})
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


if __name__ == "__main__":
    unittest.main()
