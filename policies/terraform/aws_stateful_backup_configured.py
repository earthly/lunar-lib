"""Require stateful AWS resources to declare a backup or point-in-time recovery."""

from lunar_policy import Check
from helpers import iter_resources, block, as_int, truthy


def main(node=None):
    c = Check(
        "aws-stateful-backup-configured",
        "Stateful resources declare a backup",
        node=node,
    )
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        offenders = []
        checked = 0

        # RDS instances and clusters: retention in days, 0 disables backups.
        for rtype, name, cfg in iter_resources(
            native, "aws_db_instance", "aws_rds_cluster"
        ):
            # A replica inherits its source's backups and cannot set its own.
            if cfg.get("replicate_source_db") or cfg.get("replication_source_identifier"):
                continue
            checked += 1
            if "backup_retention_period" not in cfg:
                # Declared explicitly rather than inferred from the provider
                # default: a retention window nobody wrote down is a window
                # nobody can evidence, and the default has changed before.
                offenders.append(
                    "{}.{} does not declare backup_retention_period".format(rtype, name)
                )
                continue
            days = as_int(cfg.get("backup_retention_period"))
            if days is None:
                offenders.append(
                    "{}.{} backup_retention_period is not a literal value".format(rtype, name)
                )
            elif days < 1:
                offenders.append("{}.{} retains backups for {} days".format(rtype, name, days))

        # DynamoDB: point-in-time recovery is the backup mechanism.
        for rtype, name, cfg in iter_resources(native, "aws_dynamodb_table"):
            checked += 1
            pitr = block(cfg, "point_in_time_recovery")
            if not pitr:
                offenders.append(
                    "{}.{} has no point_in_time_recovery block".format(rtype, name)
                )
            elif not any(truthy(p.get("enabled")) for p in pitr):
                offenders.append(
                    "{}.{} has point_in_time_recovery disabled".format(rtype, name)
                )

        # EFS: a backup policy, or the file system opts out explicitly.
        for rtype, name, cfg in iter_resources(native, "aws_efs_file_system"):
            checked += 1
            policies = block(cfg, "backup_policy")
            if not policies:
                offenders.append("{}.{} has no backup_policy block".format(rtype, name))
            elif not any(str(p.get("status", "")).upper() == "ENABLED" for p in policies):
                offenders.append("{}.{} has backup_policy disabled".format(rtype, name))

        if not checked:
            c.skip("No stateful resources found")

        if offenders:
            c.fail(
                "Stateful resources without a declared backup: {}. Set a non-zero "
                "backup_retention_period, enable point_in_time_recovery, or attach a "
                "backup_policy.".format(", ".join(offenders))
            )
    return c


if __name__ == "__main__":
    main()
