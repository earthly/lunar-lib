"""Require stateful AWS resources to declare a backup or point-in-time recovery."""

from lunar_policy import Check
from helpers import iter_resources, block, as_int, truthy, references


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

        # EFS backups live on a separate aws_efs_backup_policy resource keyed by
        # file_system_id, not on an inline block — correlate the two.
        backup_policies = list(iter_resources(native, "aws_efs_backup_policy"))
        for rtype, name, _ in iter_resources(native, "aws_efs_file_system"):
            checked += 1
            mine = [
                bp for _, _, bp in backup_policies
                if references(bp.get("file_system_id"), "aws_efs_file_system", name)
            ]
            if not mine:
                offenders.append(
                    "{}.{} has no aws_efs_backup_policy".format(rtype, name)
                )
                continue
            enabled = any(
                str(b.get("status", "")).upper() == "ENABLED"
                for bp in mine
                for b in block(bp, "backup_policy")
            )
            if not enabled:
                offenders.append(
                    "{}.{} has its aws_efs_backup_policy disabled".format(rtype, name)
                )

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
