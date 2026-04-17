from lunar_policy import Check


def main(node=None):
    c = Check(
        "dep-update-tool-configured",
        "Dependabot or Renovate must be configured",
        node=node,
    )
    with c:
        dependabot = (
            c.get_node(".dep_automation.dependabot")
            .get_value_or_default(".", None)
        )
        renovate = (
            c.get_node(".dep_automation.renovate")
            .get_value_or_default(".", None)
        )

        if dependabot is None and renovate is None:
            c.fail(
                "No dependency update tool configured. Add a "
                ".github/dependabot.yml or renovate.json to automate "
                "dependency updates."
            )

    return c


if __name__ == "__main__":
    main()
