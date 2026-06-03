"""Require EKS clusters to enable control-plane logging to CloudWatch."""

from lunar_policy import Check, variable_or_default
from helpers import iter_resources


def main(node=None):
    c = Check("eks-control-plane-logging", "EKS control-plane logging enabled", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        clusters = list(iter_resources(native, "aws_eks_cluster"))
        if not clusters:
            c.skip("No aws_eks_cluster resources found")

        required = [
            t.strip()
            for t in variable_or_default(
                "eks_required_log_types", "api,audit,authenticator,controllerManager,scheduler"
            ).split(",")
            if t.strip()
        ]

        for _, name, cfg in clusters:
            enabled = cfg.get("enabled_cluster_log_types")
            enabled = enabled if isinstance(enabled, list) else []
            missing = [t for t in required if t not in enabled]
            if missing:
                c.fail(
                    "aws_eks_cluster.{} is missing control-plane log types {}. Set "
                    "enabled_cluster_log_types to ship them to CloudWatch.".format(
                        name, ", ".join(missing)
                    )
                )
    return c


if __name__ == "__main__":
    main()
