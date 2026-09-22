"""Require negotiated TLS to come from an approved policy, not just be present."""

from lunar_policy import Check, variable_or_default
from helpers import iter_resources, block


_SECURE = ("https", "tls", "ssl")


def _approved(value, allowed):
    return str(value).strip() in allowed


def main(node=None):
    c = Check("aws-tls-policy-approved", "TLS uses an approved policy", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        allowed = {
            s.strip()
            for s in variable_or_default("approved_tls_policies", "").split(",")
            if s.strip()
        }
        # The approved set is the customer's cryptographic standard, not ours —
        # there is no safe default to assume on their behalf.
        if not allowed:
            c.skip("No approved TLS policies configured")

        offenders = []
        checked = 0

        # ALB/NLB: ssl_policy names the protocol-and-cipher suite.
        for rtype, name, cfg in iter_resources(native, "aws_lb_listener", "aws_alb_listener"):
            if str(cfg.get("protocol", "")).lower() not in _SECURE:
                continue  # plaintext listeners are aws-elb-https-only's business
            checked += 1
            policy = cfg.get("ssl_policy")
            if policy is None:
                offenders.append("{}.{} sets no ssl_policy".format(rtype, name))
            elif not _approved(policy, allowed):
                offenders.append("{}.{} uses {}".format(rtype, name, policy))

        # CloudFront: the floor lives on the viewer certificate.
        for rtype, name, cfg in iter_resources(native, "aws_cloudfront_distribution"):
            for cert in block(cfg, "viewer_certificate"):
                if cert.get("cloudfront_default_certificate") is not None:
                    continue  # the default cert pins its own policy
                checked += 1
                version = cert.get("minimum_protocol_version")
                if version is None:
                    offenders.append("{}.{} sets no minimum_protocol_version".format(rtype, name))
                elif not _approved(version, allowed):
                    offenders.append("{}.{} uses {}".format(rtype, name, version))

        # API Gateway custom domains carry their own security_policy.
        for rtype, name, cfg in iter_resources(
            native, "aws_api_gateway_domain_name", "aws_apigatewayv2_domain_name"
        ):
            policies = [cfg.get("security_policy")] if "security_policy" in cfg else []
            for dc in block(cfg, "domain_name_configuration"):
                policies.append(dc.get("security_policy"))
            for policy in policies:
                checked += 1
                if policy is None:
                    offenders.append("{}.{} sets no security_policy".format(rtype, name))
                elif not _approved(policy, allowed):
                    offenders.append("{}.{} uses {}".format(rtype, name, policy))

        if not checked:
            c.skip("No TLS-terminating resources found")

        if offenders:
            c.fail(
                "TLS policies outside the approved set ({}): {}. Set an approved "
                "policy, or add the one in use to the approved_tls_policies input "
                "if it meets the standard.".format(", ".join(sorted(allowed)), ", ".join(offenders))
            )
    return c


if __name__ == "__main__":
    main()
