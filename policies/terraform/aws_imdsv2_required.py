"""Require IMDSv2 with a hop limit of 1 on EC2 instances and launch templates.

IMDSv1 lets any process that can make an outbound HTTP request read the
instance role's credentials; a hop limit above 1 lets a container on the host
reach the same endpoint through the pod network.
"""

from lunar_policy import Check
from helpers import iter_resources, block


def _hop_limit(meta):
    raw = meta.get("http_put_response_hop_limit")
    try:
        return int(raw)
    except (TypeError, ValueError):
        # Absent or an unresolved interpolation — AWS defaults this to 2.
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
                # Both resources default to optional IMDSv1 and hop limit 2.
                offenders.append(
                    "{}.{} (no metadata_options)".format(rtype, name)
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
                if hops is None or hops > 1:
                    offenders.append(
                        "{}.{} hop limit {}".format(
                            rtype, name, "unset" if hops is None else hops
                        )
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
