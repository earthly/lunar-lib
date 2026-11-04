"""Require load balancers to have access logging enabled."""

from lunar_policy import Check
from helpers import iter_resources, block, truthy


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
        if not lbs:
            c.skip("No Application or Classic Load Balancers found")

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
    return c


if __name__ == "__main__":
    main()
