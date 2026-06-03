"""Require internet-facing Application Load Balancers to have a WAF web ACL."""

from lunar_policy import Check
from helpers import iter_resources, references, truthy


def main(node=None):
    c = Check("alb-waf-enabled", "Public ALBs have a WAF web ACL associated", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        albs = []
        for _, name, cfg in iter_resources(native, "aws_lb", "aws_alb"):
            if str(cfg.get("load_balancer_type", "application")).lower() != "application":
                continue
            if truthy(cfg.get("internal", False)):
                continue  # internal LBs aren't internet-facing
            albs.append(name)

        if not albs:
            c.skip("No internet-facing application load balancers found")

        targets = [
            cfg.get("resource_arn") or cfg.get("load_balancer_arn")
            for _, _, cfg in iter_resources(
                native, "aws_wafv2_web_acl_association", "aws_wafregional_web_acl_association"
            )
        ]

        unprotected = [
            "aws_lb.{}".format(name)
            for name in albs
            if not any(references(t, "aws_lb", name) or references(t, "aws_alb", name) for t in targets)
        ]
        if unprotected:
            c.fail(
                "Internet-facing ALBs without a WAF web ACL association: {}. "
                "Associate an aws_wafv2_web_acl via aws_wafv2_web_acl_association.".format(
                    ", ".join(unprotected)
                )
            )
    return c


if __name__ == "__main__":
    main()
