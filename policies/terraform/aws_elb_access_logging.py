"""Require load balancers to have access logging enabled."""

from lunar_policy import Check
from helpers import iter_resources, block, lbc_albs, truthy


def main(node=None):
    c = Check("aws-elb-access-logging", "Load balancers have access logging enabled", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        # Application (the aws_lb default) and Classic Load Balancers only, the
        # scope of Security Hub ELB.5. NLBs write access logs only for TLS
        # listeners; Gateway Load Balancers write none.
        lbs = [
            (rtype, name, cfg)
            for rtype, name, cfg in iter_resources(native, "aws_lb", "aws_alb", "aws_elb")
            if rtype == "aws_elb"
            or str(cfg.get("load_balancer_type", "application")).lower() not in ("network", "gateway")
        ]
        # ALBs the AWS Load Balancer Controller builds from Ingress resources,
        # internal ones included.
        ingress_albs = lbc_albs(native)
        if not lbs and not ingress_albs:
            c.skip("No Application or Classic Load Balancers (including Load Balancer Controller Ingress ALBs) found")

        for rtype, name, cfg in lbs:
            logs = block(cfg, "access_logs")
            # access_logs.enabled defaults to FALSE for aws_lb/aws_alb in the AWS
            # provider (a bucket alone does not turn logging on), but defaults to
            # TRUE for the classic aws_elb when the block is present.
            default_enabled = rtype == "aws_elb"
            ok = any(truthy(b.get("enabled", default_enabled)) and b.get("bucket") for b in logs)
            if not ok:
                c.fail(
                    "{}.{} has no access logging. Add an access_logs block with "
                    "enabled = true and a bucket.".format(rtype, name)
                )

        for alb in ingress_albs:
            if alb["access_logs"] is False:
                c.fail(
                    "{} has no access logging. Add access_logs.s3.enabled=true and an "
                    "access_logs.s3.bucket to the alb.ingress.kubernetes.io/load-balancer-attributes "
                    "annotation.".format(alb["label"])
                )
    return c


if __name__ == "__main__":
    main()
