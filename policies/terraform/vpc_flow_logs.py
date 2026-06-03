"""Require every VPC to have flow logs enabled."""

from lunar_policy import Check
from helpers import iter_resources, references


def main(node=None):
    c = Check("vpc-flow-logs", "VPCs have flow logs enabled", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        vpcs = list(iter_resources(native, "aws_vpc"))
        if not vpcs:
            c.skip("No aws_vpc resources found")

        flow_logs = list(iter_resources(native, "aws_flow_log"))
        for _, vname, _ in vpcs:
            if not any(references(fl.get("vpc_id"), "aws_vpc", vname) for _, _, fl in flow_logs):
                c.fail("aws_vpc.{} has no aws_flow_log capturing its traffic.".format(vname))
    return c


if __name__ == "__main__":
    main()
