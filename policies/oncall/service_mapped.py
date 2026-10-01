from lunar_policy import Check

PAGERDUTY_HINT = (
    "Annotate its Backstage Component, System or Domain with "
    "pagerduty.com/service-id, or set the pagerduty/service-id meta or the "
    "collector's service_id input."
)


def unmapped_message(c, unmapped):
    tool = c.get_node(".oncall.source.tool")
    pagerduty = tool.exists() and tool.get_value() == "pagerduty"
    what = "PagerDuty service" if pagerduty else "on-call service"
    searched = unmapped.get_value_or_default(".searched", [])
    if not isinstance(searched, list):
        searched = []
    # The code and cron collectors can both write the list; drop repeats.
    places = list(dict.fromkeys(s for s in searched if isinstance(s, str)))
    where = f" (looked in: {', '.join(places)})" if places else ""
    hint = PAGERDUTY_HINT if pagerduty else "Map it in your on-call collector's configuration."
    return f"No {what} is mapped to this component{where}. {hint}"


def main(node=None):
    c = Check("service-mapped", "Component is mapped to an on-call service", node=node)
    with c:
        # Pending while collection runs: another on-call collector may map it.
        mapped = c.get_node(".oncall.service.id").exists()
        message = None
        if not mapped:
            unmapped = c.get_node(".oncall.unmapped")
            if not unmapped.exists():
                # No collector looked for a mapping: none is configured for
                # this component, or its lookup couldn't complete. The other
                # oncall checks already fail on the missing data; failing here
                # too would report a missing mapping nobody checked for.
                c.skip(
                    "No on-call collector reported a service lookup for this "
                    "component (none is configured for it, or its lookup "
                    "could not complete)"
                )
            message = unmapped_message(c, unmapped)
        c.assert_true(mapped, message)
    return c


if __name__ == "__main__":
    main()
