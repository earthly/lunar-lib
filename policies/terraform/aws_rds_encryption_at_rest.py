"""Require RDS instances/clusters to encrypt storage at rest."""

from lunar_policy import Check
from helpers import iter_resources, iter_module_calls, truthy


def main(node=None):
    c = Check("aws-rds-encryption-at-rest", "RDS storage is encrypted at rest", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        dbs = list(iter_resources(native, "aws_db_instance", "aws_rds_cluster"))
        rds_modules = list(iter_module_calls(native, "terraform-aws-modules/rds"))
        if not dbs and not rds_modules:
            c.skip("No RDS instances or clusters found")

        for rtype, name, cfg in dbs:
            # Replicas and snapshot/PITR restores inherit encryption from their
            # source and cannot set storage_encrypted themselves.
            if cfg.get("replicate_source_db") or cfg.get("snapshot_identifier") \
                    or cfg.get("restore_to_point_in_time"):
                continue
            if not truthy(cfg.get("storage_encrypted", False)):
                c.fail(
                    "{}.{} is not encrypted at rest. Set storage_encrypted = "
                    "true.".format(rtype, name)
                )

        for mname, cfg in rds_modules:
            if not truthy(cfg.get("storage_encrypted", False)):
                c.fail(
                    "module.{} (terraform-aws-modules/rds) does not set "
                    "storage_encrypted = true.".format(mname)
                )
    return c


if __name__ == "__main__":
    main()
