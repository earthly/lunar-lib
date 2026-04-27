import re

from lunar_policy import Check, variable_or_default


def main(node=None, pager_handle_prefixes_override=None):
    c = Check(
        "monitor-has-pager-target",
        "Datadog monitors route to a pager target",
        node=node,
    )
    with c:
        monitors_node = c.get_node(".observability.native.datadog.api.monitors")
        if not monitors_node.exists():
            c.skip(
                "No Datadog monitor data — Datadog collector hasn't written native data"
            )

        prefixes_raw = (
            pager_handle_prefixes_override
            if pager_handle_prefixes_override is not None
            else variable_or_default(
                "pager_handle_prefixes", "pagerduty,opsgenie,victorops"
            )
        )
        prefixes = [p.strip() for p in prefixes_raw.split(",") if p.strip()]
        patterns = [re.compile(rf"@{re.escape(p)}-\S+") for p in prefixes]
        handles_listed = ", ".join(f"@{p}-*" for p in prefixes)

        for monitor in monitors_node:
            mid = monitor.get_value(".id")
            mname = monitor.get_value(".name")
            message_node = monitor.get_node(".message")
            message = message_node.get_value() if message_node.exists() else ""
            has_pager = any(pat.search(message or "") for pat in patterns)
            c.assert_true(
                has_pager,
                f'Monitor {mid} ("{mname}") has no pager handle in its '
                f"message (looked for {handles_listed})",
            )
    return c


if __name__ == "__main__":
    main()
