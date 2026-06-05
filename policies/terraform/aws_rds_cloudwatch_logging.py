"""Require RDS instances/clusters to export logs to CloudWatch."""

from lunar_policy import Check
from helpers import iter_resources, iter_module_calls


def _exports_missing(cfg):
    exports = cfg.get("enabled_cloudwatch_logs_exports")
    return not (isinstance(exports, list) and len(exports) > 0)


def main(node=None):
    c = Check("aws-rds-cloudwatch-logging", "RDS exports logs to CloudWatch", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        dbs = list(iter_resources(native, "aws_db_instance", "aws_rds_cluster"))
        # terraform-aws-modules/rds and /rds-aurora use the same arg name.
        rds_modules = list(iter_module_calls(native, "terraform-aws-modules/rds"))
        if not dbs and not rds_modules:
            c.skip("No RDS instances or clusters found")

        for rtype, name, cfg in dbs:
            if _exports_missing(cfg):
                c.fail(
                    "{}.{} has no enabled_cloudwatch_logs_exports. Export engine logs "
                    "(e.g. postgresql, upgrade) to CloudWatch.".format(rtype, name)
                )

        for mname, cfg in rds_modules:
            if _exports_missing(cfg):
                c.fail(
                    "module.{} (terraform-aws-modules/rds) has no "
                    "enabled_cloudwatch_logs_exports.".format(mname)
                )
    return c


if __name__ == "__main__":
    main()
