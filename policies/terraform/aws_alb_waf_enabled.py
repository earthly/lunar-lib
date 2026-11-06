"""Require internet-facing Application Load Balancers to have a WAF web ACL."""

from lunar_policy import Check
from helpers import iter_resources, lbc_albs, references, truthy


def main(node=None):
    c = Check("aws-alb-waf-enabled", "Public ALBs have a WAF web ACL associated", node=node)
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

        # ALBs the AWS Load Balancer Controller builds from Ingress resources.
        ingress_albs = [a for a in lbc_albs(native) if a["scheme"] == "internet-facing"]

        if not albs and not ingress_albs:
            c.skip("No internet-facing application load balancers (aws_lb or Load Balancer Controller Ingress) found")

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
        # An association with a looked-up ALB (data.aws_lb, usually found by the
        # controller's tags) may cover an Ingress ALB, so don't fail those then.
        looked_up = any(references(t, "data.aws_lb") or references(t, "data.aws_alb") for t in targets)
        unprotected += [a["label"] for a in ingress_albs if a["waf"] is False and not looked_up]

        if unprotected:
            c.fail(
                "Internet-facing ALBs without a WAF web ACL: {}. Associate an aws_wafv2_web_acl "
                "via aws_wafv2_web_acl_association, or set the alb.ingress.kubernetes.io/wafv2-acl-arn "
                "annotation on a Load Balancer Controller Ingress.".format(", ".join(unprotected))
            )
    return c


if __name__ == "__main__":
    main()
