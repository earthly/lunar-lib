"""Require EBS volumes (and instance block devices) to be encrypted at rest."""

from lunar_policy import Check
from helpers import as_blocks, iter_module_calls, iter_resources, block, truthy


EKS_MODULE = "terraform-aws-modules/eks/aws"
# Standalone node-group submodules take the node-group arguments directly.
NODE_GROUP_MODULES = (
    "terraform-aws-modules/eks/aws//modules/eks-managed-node-group",
    "terraform-aws-modules/eks/aws//modules/self-managed-node-group",
)
# Node-group maps on the cluster module, each with the v20 defaults map whose
# arguments a group falls back to.
NODE_GROUP_ARGS = (
    ("eks_managed_node_groups", "eks_managed_node_group_defaults"),
    ("self_managed_node_groups", "self_managed_node_group_defaults"),
)


def _bool(value, default):
    """A literal boolean (or the default when unset), or None for an expression."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return {"true": True, "false": False}.get(text)


def _node_group_encrypted(group, defaults):
    """Whether a node group's volumes are encrypted: True, False, or None if unknown.

    The node group's launch template takes block_device_mappings (a map of name
    to {device_name, ebs}). With no mapping, or with the EKS default launch
    template, the root volume is whatever the AMI says.
    """
    if not isinstance(group, dict):
        return None

    def arg(key):
        if key in group:
            return group[key]
        return defaults.get(key) if isinstance(defaults, dict) else None

    use_custom = _bool(arg("use_custom_launch_template"), True)
    create = _bool(arg("create_launch_template"), True)
    if use_custom is None or create is None:
        return None
    if not use_custom:
        return False  # EKS default launch template: block_device_mappings unused
    if not create:
        return None  # an existing launch template (launch_template_id) decides

    mappings = arg("block_device_mappings")
    if mappings is None:
        return False
    if isinstance(mappings, dict):
        mappings = list(mappings.values())
    if not isinstance(mappings, list):
        return None
    saw_ebs = False
    for m in mappings:
        if not isinstance(m, dict):
            return None
        ebs = m.get("ebs")
        if ebs is None:
            continue  # instance store or no_device
        if not as_blocks(ebs):
            return None
        for e in as_blocks(ebs):
            encrypted = _bool(e.get("encrypted"), False)
            if encrypted is None:
                return None
            if not encrypted:
                return False
            saw_ebs = True
    return saw_ebs


def _node_groups(native):
    """Yield ``(label, encrypted)`` for each EKS-module node group."""
    for mname, cfg in iter_module_calls(native, EKS_MODULE):
        for groups_key, defaults_key in NODE_GROUP_ARGS:
            groups = cfg.get(groups_key)
            if not isinstance(groups, dict):
                continue  # unset, or an expression we can't evaluate
            for gname, group in groups.items():
                label = "module.{}.{}.{}".format(mname, groups_key, gname)
                yield label, _node_group_encrypted(group, cfg.get(defaults_key))
    for mname, cfg in iter_module_calls(native, *NODE_GROUP_MODULES):
        yield "module.{}".format(mname), _node_group_encrypted(cfg, None)


def main(node=None):
    c = Check("aws-ebs-volume-encryption", "EBS volumes are encrypted at rest", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        offenders = []
        found = False

        # aws_ebs_encryption_by_default (enabled defaults to true) encrypts every
        # new volume in the account and region. It covers the volumes this
        # config leaves to the AMI: instance roots without a root_block_device,
        # and node groups without an encrypted block device mapping.
        account_default = any(
            _bool(cfg.get("enabled"), True) is not False
            for _, _, cfg in iter_resources(native, "aws_ebs_encryption_by_default")
        )
        covered = []

        def implicit(label):
            (covered if account_default else offenders).append(label)

        for _, name, cfg in iter_resources(native, "aws_ebs_volume"):
            found = True
            if not truthy(cfg.get("encrypted", False)):
                offenders.append("aws_ebs_volume.{}".format(name))

        for _, name, cfg in iter_resources(native, "aws_instance"):
            found = True
            roots = block(cfg, "root_block_device")
            for dev in roots + block(cfg, "ebs_block_device"):
                if not truthy(dev.get("encrypted", False)):
                    offenders.append("aws_instance.{} block device".format(name))
                    break
            # A launch template's block_device_mappings (checked below) decide
            # the root volume of an instance launched from one.
            if not roots and not block(cfg, "launch_template"):
                implicit("aws_instance.{} root volume (no root_block_device)".format(name))

        for _, name, cfg in iter_resources(native, "aws_launch_template"):
            for bdm in block(cfg, "block_device_mappings"):
                for ebs in block(bdm, "ebs"):
                    found = True
                    if not truthy(ebs.get("encrypted", False)):
                        offenders.append("aws_launch_template.{} ebs".format(name))
                        break

        for label, encrypted in _node_groups(native):
            if encrypted is None:
                continue
            found = True
            if not encrypted:
                implicit("{} (no encrypted block_device_mappings)".format(label))

        if not found:
            c.skip("No EBS volumes, instances, launch templates or EKS node groups found")

        if offenders:
            note = ""
            if covered:
                note = " ({} covered by aws_ebs_encryption_by_default)".format(", ".join(sorted(covered)))
            c.fail(
                "Unencrypted EBS volumes/block devices: {}. Set encrypted = true, or enable "
                "aws_ebs_encryption_by_default for volumes left to the AMI default.{}".format(
                    ", ".join(sorted(set(offenders))), note
                )
            )
    return c


if __name__ == "__main__":
    main()
