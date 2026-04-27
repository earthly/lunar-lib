import re

from lunar_policy import Check


SLO_ID_RE = re.compile(r'(?:burn_rate|error_budget)\s*\(\s*"([^"]+)"')


def main(node=None):
    c = Check(
        "slo-burn-rate-alert",
        "Each Datadog SLO has a matching burn-rate alert monitor",
        node=node,
    )
    with c:
        slos_node = c.get_node(".observability.native.datadog.api.slos")
        if not slos_node.exists():
            c.skip(
                "No Datadog SLO data — Datadog collector hasn't written native data"
            )

        slo_defined_node = c.get_node(".observability.slo.defined")
        if not slo_defined_node.exists() or not bool(slo_defined_node.get_value()):
            c.skip("No SLOs defined for this service")

        referenced_slo_ids = set()
        monitors_node = c.get_node(".observability.native.datadog.api.monitors")
        if monitors_node.exists():
            for m in monitors_node:
                m_type_node = m.get_node(".type")
                if not m_type_node.exists() or m_type_node.get_value() != "slo alert":
                    continue
                query_node = m.get_node(".query")
                if not query_node.exists():
                    continue
                q = query_node.get_value() or ""
                match = SLO_ID_RE.search(q)
                if match:
                    referenced_slo_ids.add(match.group(1))

        for slo in slos_node:
            sid = slo.get_value(".id")
            sname = slo.get_value(".name")
            c.assert_true(
                sid in referenced_slo_ids,
                f'SLO {sid} ("{sname}") has no matching burn-rate alert monitor',
            )
    return c


if __name__ == "__main__":
    main()
