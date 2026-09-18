"""Require IMDSv2 on EC2 instances and launch templates, with no extra hops.

IMDSv1 lets any process that can make an outbound HTTP request read the
instance role's credentials, and `http_tokens` defaults to "optional" — so an
absent metadata_options block leaves IMDSv1 reachable.

The hop limit defaults to 1, which is already the safe value, so this only
objects to an explicit hop limit above 1. (EKS managed node groups are the
common source of 2, where it lets a pod reach the node role.)
"""

from lunar_policy import Check
from helpers import iter_resources, block


_ABSENT = object()


def _hop_limit(meta):
    """Return the hop limit, `_ABSENT` if unset, or None if unparseable.

    Unset is safe (the provider default is 1). Set-but-unparseable — an
    unresolved `${var.x}` — is unknown, which is not the same thing.
    """
    if "http_put_response_hop_limit" not in meta:
        return _ABSENT
    try:
        return int(meta["http_put_response_hop_limit"])
    except (TypeError, ValueError):
        return None


def main(node=None):
    c = Check(
        "aws-imdsv2-required",
        "EC2 metadata requires IMDSv2 with hop limit 1",
        node=node,
    )
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        offenders = []
        found = False

        for rtype, name, cfg in iter_resources(
            native, "aws_instance", "aws_launch_template"
        ):
            found = True
            metas = block(cfg, "metadata_options")
            if not metas:
                # http_tokens defaults to "optional", so IMDSv1 is reachable.
                offenders.append(
                    "{}.{} (no metadata_options, so http_tokens is optional)".format(
                        rtype, name
                    )
                )
                continue
            for meta in metas:
                tokens = str(meta.get("http_tokens", "")).strip().lower()
                if tokens != "required":
                    offenders.append(
                        "{}.{} http_tokens={}".format(
                            rtype, name, tokens or "unset"
                        )
                    )
                hops = _hop_limit(meta)
                if hops is None:
                    offenders.append(
                        "{}.{} hop limit is not a literal value".format(rtype, name)
                    )
                elif hops is not _ABSENT and hops > 1:
                    offenders.append(
                        "{}.{} hop limit {}".format(rtype, name, hops)
                    )

        if not found:
            c.skip("No EC2 instances or launch templates found")

        if offenders:
            # No .format() here: the remediation text contains literal HCL
            # braces, which str.format reads as replacement fields.
            c.fail(
                "Instance metadata reachable without IMDSv2: "
                + ", ".join(sorted(set(offenders)))
                + '. Set metadata_options { http_tokens = "required", '
                + "http_put_response_hop_limit = 1 }."
            )
    return c


if __name__ == "__main__":
    main()
