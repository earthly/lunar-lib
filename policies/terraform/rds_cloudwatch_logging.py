"""Require RDS instances/clusters to export logs to CloudWatch."""

from lunar_policy import Check
from helpers import iter_resources


def main(node=None):
    c = Check("rds-cloudwatch-logging", "RDS exports logs to CloudWatch", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        dbs = list(iter_resources(native, "aws_db_instance", "aws_rds_cluster"))
        if not dbs:
            c.skip("No RDS instances or clusters found")

        for rtype, name, cfg in dbs:
            exports = cfg.get("enabled_cloudwatch_logs_exports")
            if not (isinstance(exports, list) and len(exports) > 0):
                c.fail(
                    "{}.{} has no enabled_cloudwatch_logs_exports. Export engine logs "
                    "(e.g. postgresql, upgrade) to CloudWatch.".format(rtype, name)
                )
    return c


if __name__ == "__main__":
    main()
