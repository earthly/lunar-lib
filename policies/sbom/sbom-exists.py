from lunar_policy import Check

with Check("sbom-exists", "Checks that an SBOM was generated") as c:
    auto = c.get_node(".sbom.auto")
    cicd = c.get_node(".sbom.cicd")
    c.assert_true(
        auto.exists() or cicd.exists(),
        "No SBOM found. Enable the syft collector or run syft in your CI pipeline."
    )
