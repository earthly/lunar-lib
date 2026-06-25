import json
import os

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "gitops-managed",
        "Components expected on GitOps should be deployed by an Application",
        node=node,
    )
    with c:
        # The "expected on GitOps" set is the org's own input. If expected_tag is
        # configured, only enforce on components carrying it; otherwise enforce on
        # every component the policy targets (via `on:`).
        expected = variable_or_default("expected_tag", "").strip()
        if expected:
            tags = json.loads(os.environ.get("LUNAR_COMPONENT_TAGS", "[]"))
            if expected not in tags:
                c.skip(f"Component is not tagged '{expected}' — not expected on GitOps")

        # Inverse skip-vs-fail: absence of GitOps data is the violation here.
        # `.cd.gitops` is present when the component ships ArgoCD files OR when
        # link-push stamped its deployment posture out-of-band.
        c.assert_exists(
            ".cd.gitops",
            "Component is expected to be GitOps-managed but no Application deploys "
            "it (.cd.gitops not found). Migrate it to GitOps or exclude it from "
            "this policy's scope.",
        )
    return c


if __name__ == "__main__":
    main()
