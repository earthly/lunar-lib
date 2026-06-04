"""Forbid RDS instances/clusters from being publicly accessible."""

from lunar_policy import Check
from helpers import iter_resources, iter_module_calls, truthy


def main(node=None):
    c = Check("aws-rds-not-publicly-accessible", "RDS is not publicly accessible", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        dbs = list(iter_resources(native, "aws_db_instance", "aws_rds_cluster_instance"))
        rds_modules = list(iter_module_calls(native, "terraform-aws-modules/rds"))
        if not dbs and not rds_modules:
            c.skip("No RDS instances found")

        # publicly_accessible defaults to false; only an explicit true is a finding.
        for rtype, name, cfg in dbs:
            if truthy(cfg.get("publicly_accessible", False)):
                c.fail(
                    "{}.{} sets publicly_accessible = true. Databases must not be "
                    "reachable from the public internet.".format(rtype, name)
                )

        for mname, cfg in rds_modules:
            if truthy(cfg.get("publicly_accessible", False)):
                c.fail(
                    "module.{} (terraform-aws-modules/rds) sets publicly_accessible "
                    "= true.".format(mname)
                )
    return c


if __name__ == "__main__":
    main()
