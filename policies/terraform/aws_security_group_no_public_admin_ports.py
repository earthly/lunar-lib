"""Forbid unrestricted public ingress to sensitive admin/database ports.

Consolidates the broad family of "security group port restriction (X)" controls
into one check. SSH (22) and PostgreSQL (5432) keep their own dedicated checks
(``aws-security-group-no-public-ssh`` / ``-postgres``) and are intentionally not
repeated here.
"""

from lunar_policy import Check, variable_or_default
from helpers import public_ingress_offenders_for_ports, has_any_security_group


# port -> human-readable service. Mirrors the Secureframe port-restriction set.
_ADMIN_PORTS = {
    20: "FTP-data",
    21: "FTP",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    135: "MSRPC",
    137: "NetBIOS",
    138: "NetBIOS",
    139: "NetBIOS/CIFS",
    445: "SMB/CIFS",
    1433: "MSSQL",
    1521: "Oracle",
    2375: "Docker",
    2376: "Docker-TLS",
    3306: "MySQL",
    3389: "RDP",
    4505: "Salt",
    4506: "Salt",
    5500: "VNC-client",
    5601: "Kibana",
    5900: "VNC",
    8020: "HDFS-NameNode",
    9200: "Elasticsearch",
    9300: "Elasticsearch",
    50070: "HDFS-WebUI",
}


def main(node=None):
    c = Check(
        "aws-security-group-no-public-admin-ports",
        "No public ingress to sensitive admin/database ports",
        node=node,
    )
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        if not has_any_security_group(native):
            c.skip("No security groups found")

        ports = dict(_ADMIN_PORTS)
        extra = variable_or_default("extra_admin_ports", "").strip()
        if extra:
            for tok in extra.split(","):
                tok = tok.strip()
                if tok.isdigit():
                    ports.setdefault(int(tok), "custom")

        offenders = public_ingress_offenders_for_ports(native, list(ports))
        for port in sorted(offenders):
            labels = ", ".join(sorted(set(offenders[port])))
            c.fail(
                "Unrestricted (0.0.0.0/0 or ::/0) ingress to {} port {} in: {}. "
                "Restrict the source to known CIDRs, a bastion, or a security "
                "group.".format(ports[port], port, labels)
            )
    return c


if __name__ == "__main__":
    main()
