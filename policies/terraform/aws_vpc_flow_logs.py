"""Require every VPC to have flow logs enabled."""

from lunar_policy import Check
from helpers import iter_resources, iter_module_calls, references, truthy


def main(node=None):
    c = Check("aws-vpc-flow-logs", "VPCs have flow logs enabled", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        vpcs = list(iter_resources(native, "aws_vpc"))
        # terraform-aws-modules/vpc provisions the VPC + (optionally) flow logs.
        vpc_modules = list(iter_module_calls(native, "terraform-aws-modules/vpc"))
        if not vpcs and not vpc_modules:
            c.skip("No VPCs found")

        flow_logs = list(iter_resources(native, "aws_flow_log"))
        for _, vname, _ in vpcs:
            if not any(references(fl.get("vpc_id"), "aws_vpc", vname) for _, _, fl in flow_logs):
                c.fail("aws_vpc.{} has no aws_flow_log capturing its traffic.".format(vname))

        # The vpc module's enable_flow_log defaults to false.
        for mname, cfg in vpc_modules:
            if not truthy(cfg.get("enable_flow_log", False)):
                c.fail(
                    "module.{} (terraform-aws-modules/vpc) does not set "
                    "enable_flow_log = true.".format(mname)
                )
    return c


if __name__ == "__main__":
    main()
