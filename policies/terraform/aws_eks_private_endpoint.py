"""Require EKS clusters to enable private API-server endpoint access."""

from lunar_policy import Check
from helpers import iter_resources, iter_module_calls, block, truthy


def main(node=None):
    c = Check("aws-eks-private-endpoint", "EKS clusters enable private endpoint access", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        clusters = list(iter_resources(native, "aws_eks_cluster"))
        eks_modules = list(iter_module_calls(native, "terraform-aws-modules/eks"))
        if not clusters and not eks_modules:
            c.skip("No EKS clusters found")

        for _, name, cfg in clusters:
            # Raw aws_eks_cluster: endpoint_private_access defaults to false.
            private = any(truthy(vc.get("endpoint_private_access", False)) for vc in block(cfg, "vpc_config"))
            if not private:
                c.fail(
                    "aws_eks_cluster.{} does not enable private endpoint access "
                    "(set vpc_config.endpoint_private_access = true).".format(name)
                )

        for mname, cfg in eks_modules:
            # The module defaults cluster_endpoint_private_access to true.
            if not truthy(cfg.get("cluster_endpoint_private_access", True)):
                c.fail(
                    "module.{} sets cluster_endpoint_private_access = false.".format(mname)
                )
    return c


if __name__ == "__main__":
    main()
