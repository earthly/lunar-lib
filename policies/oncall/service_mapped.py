from lunar_policy import Check

PAGERDUTY_HINT = (
    "Annotate its Backstage Component, System or Domain with "
    "pagerduty.com/service-id, or set the pagerduty/service-id meta or the "
    "collector's service_id input."
)


def strings(value):
    """The distinct strings of a list, in order: sub-collectors can repeat entries."""
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(s for s in value if isinstance(s, str)))


def main(node=None):
    c = Check("service-mapped", "Component is mapped to an on-call service", node=node)
    with c:
        # Pending while collection runs: another on-call collector may map it.
        mapped = c.get_node(".oncall.service.id").exists()
        message = None
        if not mapped:
            lookup = c.get_node(".oncall.service_lookup")
            if not lookup.exists():
                # No collector looked for a mapping. The other oncall checks
                # already fail on the missing data; failing here too would
                # report a missing mapping nobody checked for.
                c.skip("No on-call collector looked up a service for this component")
            tool = c.get_node(".oncall.source.tool")
            pagerduty = tool.exists() and tool.get_value() == "pagerduty"
            what = "PagerDuty service" if pagerduty else "on-call service"
            errors = strings(lookup.get_value_or_default(".errors", []))
            if errors:
                # A lookup that didn't complete (e.g. Backstage was down) may
                # have held the mapping, so this can't be called unmapped.
                c.skip(f"Couldn't tell whether a {what} is mapped: {'; '.join(errors)}")
            places = strings(lookup.get_value_or_default(".searched", []))
            where = f" (looked in: {', '.join(places)})" if places else ""
            hint = PAGERDUTY_HINT if pagerduty else "Map it in your on-call collector's configuration."
            message = f"No {what} is mapped to this component{where}. {hint}"
        c.assert_true(mapped, message)
    return c


if __name__ == "__main__":
    main()
