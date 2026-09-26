import re

from lunar_policy import Check, variable_or_default

from helpers import mesh_present

# Istio's TLSProtocol names, lowest first.
VERSIONS = ["TLSV1_0", "TLSV1_1", "TLSV1_2", "TLSV1_3"]
# Gateway modes where Istio applies the server's TLS parameters, over
# meshConfig.tlsDefaults. PASSTHROUGH and AUTO_PASSTHROUGH leave TLS to the
# backend; ISTIO_MUTUAL takes no TLS parameters.
TERMINATING = {"SIMPLE", "MUTUAL", "OPTIONAL_MUTUAL"}


def configured(name):
    return {s.upper() for s in re.split(r"[\s,]+", variable_or_default(name, "") or "") if s}


def pinned(version):
    """Whether a version bounds the range; TLS_AUTO leaves the bound to the default."""
    return version not in (None, "", "TLS_AUTO")


def negotiable(floor, ceiling):
    """Every protocol version an endpoint can negotiate, lowest first."""
    if floor in VERSIONS and ceiling in VERSIONS:
        return VERSIONS[VERSIONS.index(floor):VERSIONS.index(ceiling) + 1]
    return [v for v in (floor, ceiling) if v]


def version_problem(floor, ceiling, approved, unset=""):
    if floor is None:
        return f"doesn't set minProtocolVersion{unset}"
    bad = [v for v in negotiable(floor, ceiling) if v not in approved]
    return f"allows unapproved protocol versions {', '.join(bad)}" if bad else None


def cipher_problem(ciphers, approved, unset=""):
    if not ciphers:
        return f"doesn't set cipherSuites{unset}"
    bad = [s for s in ciphers if str(s).upper() not in approved]
    return f"uses unapproved cipher suites {', '.join(bad)}" if bad else None


def main(node=None):
    """Requires configured TLS protocol versions and cipher suites to be approved."""
    c = Check("tls-approved", "TLS versions and cipher suites should be on the approved lists", node=node)
    with c:
        mesh_present(c)

        versions = configured("approved_tls_versions")
        suites = configured("approved_cipher_suites")
        unknown = sorted(versions - set(VERSIONS))
        if unknown:
            raise ValueError(f"Policy misconfiguration: approved_tls_versions has {', '.join(unknown)}; "
                             f"use Istio's names: {', '.join(VERSIONS)}")
        # The approved lists are the organisation's cryptographic standard; there
        # is no safe default to assume on its behalf.
        if not versions and not suites:
            c.skip("No approved TLS versions or cipher suites configured")

        def endpoint_problems(floor, ceiling, ciphers, unset=""):
            found = [version_problem(floor, ceiling, versions, unset)] if versions else []
            # Cipher suites only govern TLS 1.2 and below.
            if suites and floor != "TLSV1_3":
                found.append(cipher_problem(ciphers, suites, unset))
            return [f for f in found if f]

        mc_node = c.get_node(".mesh.mesh_configs")
        mesh_configs = [m.get_value() for m in mc_node] if mc_node.exists() else []
        checked = len(mesh_configs)

        for mc in mesh_configs:
            where = f"{mc.get('kind')} {mc.get('namespace', 'default')}/{mc.get('name', '<unknown>')}"

            # Mesh mTLS between sidecars; Istio caps it at TLS 1.3.
            mtls = mc.get("mesh_mtls") or {}
            floor = mtls.get("min_protocol_version")
            found = endpoint_problems(floor if pinned(floor) else None, "TLSV1_3", mtls.get("cipher_suites"))
            if found:
                c.fail(f"{where} meshConfig.meshMTLS {'; '.join(found)}")

            # tlsDefaults may leave a value unset for each server to choose;
            # whatever it does set must be approved.
            defaults = mc.get("tls_defaults") or {}
            floor, ciphers = defaults.get("min_protocol_version"), defaults.get("cipher_suites")
            found = [version_problem(floor, "TLSV1_3", versions) if versions and pinned(floor) else None,
                     cipher_problem(ciphers, suites) if suites and ciphers else None]
            found = [f for f in found if f]
            if found:
                c.fail(f"{where} meshConfig.tlsDefaults {'; '.join(found)}")

        # A Gateway server inherits tlsDefaults for what it leaves unset. With
        # several MeshConfigs in the repo, credit only what every one of them sets.
        floors = [(m.get("tls_defaults") or {}).get("min_protocol_version") for m in mesh_configs]
        inherited_floor = None
        if floors and all(pinned(f) for f in floors):
            inherited_floor = min(floors, key=lambda f: VERSIONS.index(f) if f in VERSIONS else -1)
        cipher_lists = [(m.get("tls_defaults") or {}).get("cipher_suites") for m in mesh_configs]
        inherited_ciphers = sorted({s for cl in cipher_lists for s in cl}) if cipher_lists and all(cipher_lists) else None

        gateways = c.get_node(".mesh.gateways")
        for gw in (gateways.get_value() if gateways.exists() else []):
            for s in gw.get("servers") or []:
                mode = str(s.get("tls_mode") or "").upper()
                if mode not in TERMINATING:
                    continue  # TLS isn't terminated here; gateway-tls covers plaintext servers
                checked += 1
                floor, ceiling = s.get("min_protocol_version"), s.get("max_protocol_version")
                found = endpoint_problems(floor if pinned(floor) else inherited_floor,
                                          ceiling if pinned(ceiling) else "TLSV1_3",
                                          s.get("cipher_suites") or inherited_ciphers,
                                          unset=" (on the server or in meshConfig.tlsDefaults)")
                if found:
                    c.fail(f"Gateway {gw.get('namespace', 'default')}/{gw.get('name', '<unknown>')} "
                           f"port {s.get('port', '?')} ({mode}) {'; '.join(found)}")

        if not checked:
            c.skip("No TLS-terminating Gateway servers or MeshConfig found")

    return c


if __name__ == "__main__":
    main()
