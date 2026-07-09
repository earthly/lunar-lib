from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "gitops-managed",
        "Components expected on GitOps should be deployed by an Application",
        node=node,
    )
    with c:
        # The "expected on GitOps" set is the org's own choice, scoped two ways:
        #   1. Deploy this policy `on:` the tag/domain that must be GitOps-managed
        #      (e.g. on:[production]) and leave expected_tag empty — every targeted
        #      component is then expected to have GitOps data.
        #   2. Set expected_tag to a catalog tag; the check only enforces on
        #      components whose .catalog.entity.tags carry it, skipping the rest.
        # Tags live in the Component JSON (.catalog.entity.tags, populated by a
        # catalog cataloger) — manifest `on:` tags are not visible to policy code.
        expected = variable_or_default("expected_tag", "").strip()
        if expected:
            tags = c.get_node(".catalog.entity.tags").get_value_or_default(".", []) or []
            if expected not in tags:
                c.skip(
                    f"Component is not tagged '{expected}' in the catalog — "
                    f"not expected on GitOps"
                )

        # Inverse skip-vs-fail: absence of GitOps data is the violation here.
        # `.cd.gitops` is present when the component ships ArgoCD files OR when
        # link-push stamped its deployment posture out-of-band. Assert it as an
        # explicit boolean (not assert_exists, whose missing-path result reports
        # as no-data/pending) so a component that should be on GitOps but isn't
        # surfaces as a clear failure.
        has_gitops = c.get_node(".cd.gitops").get_value_or_default(".", None) is not None
        c.assert_true(
            has_gitops,
            "Component is expected to be GitOps-managed but no Application deploys "
            "it (.cd.gitops not found). Migrate it to GitOps or exclude it from "
            "this policy's scope.",
        )
    return c


if __name__ == "__main__":
    main()
