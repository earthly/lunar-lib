from lunar_policy import Check, variable_or_default


def check_blocked_origins(node=None):
    c = Check(
        "blocked-origins",
        "Checks for dependencies with license origin mentions from blocked countries",
        node=node,
    )
    with c:
        blocked_str = variable_or_default("blocked_countries", "")
        allowed_str = variable_or_default("allowed_countries", "")

        if not blocked_str and not allowed_str:
            pass  # No countries configured — auto-pass
        else:
            origins = c.get_node(".sbom.license_origins")
            if not origins.exists():
                c.skip("No license origin data available — enable the license-origins collector")

            packages = origins.get_node(".packages")
            if not packages.exists():
                pass  # No packages with country mentions — pass
            else:
                if blocked_str:
                    blocked = {
                        s.strip().lower()
                        for s in blocked_str.split(",")
                        if s.strip()
                    }
                    seen = set()
                    for pkg in packages:
                        purl = pkg.get_value_or_default(".purl", "<unknown>")
                        if purl in seen:
                            continue
                        countries_node = pkg.get_node(".countries")
                        if not countries_node.exists():
                            continue
                        for country_node in countries_node:
                            country = country_node.get_value()
                            if country.lower() in blocked:
                                excerpts_node = pkg.get_node(".excerpts")
                                excerpt = ""
                                if excerpts_node.exists():
                                    for e in excerpts_node:
                                        excerpt = e.get_value()
                                        break
                                msg = (
                                    f"Package '{purl}' has license origin mention "
                                    f"for blocked country '{country}'"
                                )
                                if excerpt:
                                    msg += f": \"{excerpt}\""
                                c.fail(msg)
                                seen.add(purl)
                                break
                elif allowed_str:
                    allowed = {
                        s.strip().lower()
                        for s in allowed_str.split(",")
                        if s.strip()
                    }
                    seen = set()
                    for pkg in packages:
                        purl = pkg.get_value_or_default(".purl", "<unknown>")
                        if purl in seen:
                            continue
                        countries_node = pkg.get_node(".countries")
                        if not countries_node.exists():
                            continue
                        for country_node in countries_node:
                            country = country_node.get_value()
                            if country.lower() not in allowed:
                                c.fail(
                                    f"Package '{purl}' has license origin mention "
                                    f"for non-allowed country '{country}'"
                                )
                                seen.add(purl)
                                break
    return c


if __name__ == "__main__":
    check_blocked_origins()
