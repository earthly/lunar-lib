from lunar_policy import Check


def main(node=None):
    c = Check(
        "valid",
        "ArgoCD manifests should conform to the argoproj CRD schemas",
        node=node,
    )
    with c:
        if c.get_node(".cd.gitops").get_value_or_default(".", None) is None:
            c.skip("No GitOps (.cd.gitops) data — vendor not in use")

        for collection in ("applications", "projects"):
            items = c.get_node(f".cd.gitops.{collection}")
            if not items.exists():
                continue
            for item in items:
                name = item.get_value_or_default(".name", "<unknown>")
                path = item.get_value_or_default(".path", "<unknown>")
                valid = item.get_value_or_default(".valid", True)
                c.assert_true(
                    bool(valid),
                    f"{path}: '{name}' is not a valid argoproj resource",
                )
    return c


if __name__ == "__main__":
    main()
