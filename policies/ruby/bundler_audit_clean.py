from lunar_policy import Check, variable_or_default


def check_bundler_audit_clean(max_vulnerabilities=None, node=None):
    """Check that bundler-audit reports no known vulnerabilities."""
    if max_vulnerabilities is None:
        max_vulnerabilities = int(
            variable_or_default("max_audit_vulnerabilities", "0")
        )
    else:
        max_vulnerabilities = int(max_vulnerabilities)

    c = Check(
        "bundler-audit-clean",
        "Ensures no known vulnerabilities in gem dependencies",
        node=node,
    )
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")

        audit = ruby.get_node(".bundler_audit")
        if not audit.exists():
            c.skip(
                "No bundler-audit data available. Enable the bundler-audit "
                "sub-collector or run 'bundle audit' in CI."
            )

        vulns = audit.get_node(".vulnerabilities")
        if not vulns.exists():
            c.skip("Bundler-audit data incomplete")

        vuln_list = vulns.get_value()
        count = len(vuln_list) if vuln_list else 0

        if count > max_vulnerabilities:
            c.fail(
                f"bundler-audit found {count} known vulnerability(ies), "
                f"maximum allowed is {max_vulnerabilities}. "
                f"Run 'bundle audit' for details and update affected gems."
            )
    return c


if __name__ == "__main__":
    check_bundler_audit_clean()
