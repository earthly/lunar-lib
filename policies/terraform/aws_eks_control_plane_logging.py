"""Require EKS clusters to enable control-plane logging to CloudWatch."""

from lunar_policy import Check, variable_or_default
from helpers import iter_resources, iter_module_calls, first_set


# terraform-aws-modules/eks enables these by default when the caller omits
# enabled_log_types (v21) / cluster_enabled_log_types (v20).
_EKS_MODULE_DEFAULT = ["audit", "api", "authenticator"]


def main(node=None):
    c = Check("aws-eks-control-plane-logging", "EKS control-plane logging enabled", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        clusters = list(iter_resources(native, "aws_eks_cluster"))
        eks_modules = list(iter_module_calls(native, "terraform-aws-modules/eks/aws"))
        if not clusters and not eks_modules:
            c.skip("No EKS clusters found")

        required = [
            t.strip()
            for t in variable_or_default(
                "eks_required_log_types", "api,audit,authenticator,controllerManager,scheduler"
            ).split(",")
            if t.strip()
        ]

        def missing_from(enabled, label):
            enabled = enabled if isinstance(enabled, list) else []
            missing = [t for t in required if t not in enabled]
            if missing:
                c.fail(
                    "{} is missing control-plane log types {}. Set "
                    "(cluster_)enabled_(cluster_)log_types to ship them to "
                    "CloudWatch.".format(label, ", ".join(missing))
                )

        for _, name, cfg in clusters:
            missing_from(cfg.get("enabled_cluster_log_types"), "aws_eks_cluster.{}".format(name))

        for mname, cfg in eks_modules:
            _, enabled = first_set(
                cfg, ("enabled_log_types", "cluster_enabled_log_types"), _EKS_MODULE_DEFAULT
            )
            missing_from(enabled, "module.{} (terraform-aws-modules/eks)".format(mname))
    return c


if __name__ == "__main__":
    main()
