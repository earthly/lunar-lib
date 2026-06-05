"""Require RDS snapshots to be encrypted at rest (via their source DB).

RDS snapshots have no ``encrypted`` argument of their own — they inherit
encryption from the source instance/cluster. So this check resolves each
snapshot's source within the same config and requires it to be encrypted.
"""

from lunar_policy import Check
from helpers import iter_resources, references, truthy


def _encrypted_sources(native, rtype):
    return {
        name: truthy(cfg.get("storage_encrypted", False))
        for _, name, cfg in iter_resources(native, rtype)
    }


def main(node=None):
    c = Check("aws-rds-snapshot-encryption", "RDS snapshots are encrypted at rest", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        snaps = list(iter_resources(native, "aws_db_snapshot", "aws_db_cluster_snapshot"))
        if not snaps:
            c.skip("No RDS snapshot resources found")

        instances = _encrypted_sources(native, "aws_db_instance")
        clusters = _encrypted_sources(native, "aws_rds_cluster")

        for rtype, name, cfg in snaps:
            if rtype == "aws_db_snapshot":
                src_ref, sources, src_type = cfg.get("db_instance_identifier"), instances, "aws_db_instance"
            else:
                src_ref, sources, src_type = cfg.get("db_cluster_identifier"), clusters, "aws_rds_cluster"

            matched = [enc for sname, enc in sources.items() if references(src_ref, src_type, sname)]
            if not matched:
                # Source is an external/literal identifier we cannot inspect.
                continue
            if not all(matched):
                c.fail(
                    "{}.{} snapshots an unencrypted {} (storage_encrypted is not "
                    "true); the snapshot inherits that.".format(rtype, name, src_type)
                )
    return c


if __name__ == "__main__":
    main()
