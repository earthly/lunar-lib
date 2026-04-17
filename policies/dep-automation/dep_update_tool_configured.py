from lunar_policy import Check


def _bool_true(c, path):
    node = c.get_node(path)
    if not node.exists():
        return False
    return bool(node.get_value())


def main(node=None):
    c = Check(
        "dep-update-tool-configured",
        "Dependabot or Renovate must be configured",
        node=node,
    )
    with c:
        dependabot = _bool_true(c, ".dep_automation.dependabot.exists")
        renovate = _bool_true(c, ".dep_automation.renovate.exists")

        if not dependabot and not renovate:
            c.fail(
                "No dependency update tool configured. Add a "
                ".github/dependabot.yml or renovate.json to automate "
                "dependency updates."
            )

    return c


if __name__ == "__main__":
    main()
