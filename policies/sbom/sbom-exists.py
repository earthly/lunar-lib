from lunar_policy import Check

with Check("sbom-exists", "Checks that an SBOM was generated") as c:
    c.assert_exists(".sbom")
