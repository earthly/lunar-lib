"""Require EBS snapshots to be encrypted at rest."""

from lunar_policy import Check
from helpers import iter_resources, truthy


def main(node=None):
    c = Check("aws-ebs-snapshot-encryption", "EBS snapshots are encrypted at rest", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        snaps = list(iter_resources(native, "aws_ebs_snapshot", "aws_ebs_snapshot_copy"))
        if not snaps:
            c.skip("No EBS snapshot resources found")

        for rtype, name, cfg in snaps:
            if not truthy(cfg.get("encrypted", False)):
                c.fail("{}.{} is not encrypted at rest. Set encrypted = true.".format(rtype, name))
    return c


if __name__ == "__main__":
    main()
