"""Require EBS volumes (and instance block devices) to be encrypted at rest."""

from lunar_policy import Check
from helpers import iter_resources, block, truthy


def main(node=None):
    c = Check("aws-ebs-volume-encryption", "EBS volumes are encrypted at rest", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        offenders = []
        found = False

        for _, name, cfg in iter_resources(native, "aws_ebs_volume"):
            found = True
            if not truthy(cfg.get("encrypted", False)):
                offenders.append("aws_ebs_volume.{}".format(name))

        for _, name, cfg in iter_resources(native, "aws_instance"):
            for dev in block(cfg, "root_block_device") + block(cfg, "ebs_block_device"):
                found = True
                if not truthy(dev.get("encrypted", False)):
                    offenders.append("aws_instance.{} block device".format(name))
                    break

        for _, name, cfg in iter_resources(native, "aws_launch_template"):
            for bdm in block(cfg, "block_device_mappings"):
                for ebs in block(bdm, "ebs"):
                    found = True
                    if not truthy(ebs.get("encrypted", False)):
                        offenders.append("aws_launch_template.{} ebs".format(name))
                        break

        if not found:
            c.skip("No EBS volumes or instance block devices found")

        if offenders:
            c.fail(
                "Unencrypted EBS volumes/block devices: {}. Set encrypted = true.".format(
                    ", ".join(sorted(set(offenders)))
                )
            )
    return c


if __name__ == "__main__":
    main()
