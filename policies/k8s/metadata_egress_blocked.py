import ipaddress

from lunar_policy import Check, variable_or_default

from helpers import selector_matches

# The instance-metadata service answers plain HTTP on port 80
# (http://169.254.169.254/latest/meta-data/), so a rule limited to other ports
# does not reach it.
METADATA_PORT = 80


def metadata_ips():
    raw = variable_or_default("metadata_ips", "169.254.169.254") or ""
    ips = []
    for value in raw.replace(",", " ").split():
        try:
            ips.append(ipaddress.ip_address(value))
        except ValueError:
            raise ValueError(f"Policy misconfiguration: metadata_ips entry {value!r} is not an IP address")
    if not ips:
        raise ValueError("Policy misconfiguration: metadata_ips is empty")
    return ips


def covers(cidr, ip):
    """Whether the CIDR contains ip; None when it doesn't parse."""
    try:
        return ip in ipaddress.ip_network(str(cidr), strict=False)
    except ValueError:
        return None


def reaches_port(ports):
    if not ports:
        return True  # no ports listed: every port
    for p in ports:
        if str(p.get("protocol") or "TCP").upper() != "TCP":
            continue
        port = p.get("port")
        if port is None:
            return True  # a protocol with no port: every port of it
        if isinstance(port, str) and port.isdigit():
            port = int(port)
        if not isinstance(port, int):
            continue  # a named port resolves against the destination pod's ports
        end = p.get("endPort")
        if port == METADATA_PORT or (isinstance(end, int) and port <= METADATA_PORT <= end):
            return True
    return False


def opening(rule, ip):
    """How an egress rule admits traffic to ip, or None if it doesn't."""
    if not reaches_port(rule.get("ports")):
        return None
    peers = rule.get("to")
    if not peers:
        return "has an egress rule with no `to`, which allows every destination"
    for peer in peers:
        block = peer.get("ipBlock")
        if not block:
            continue  # pod and namespace selectors match pods, never the metadata IP
        cidr = block.get("cidr")
        if covers(cidr, ip) is False:
            continue
        if any(covers(e, ip) for e in block.get("except") or []):
            continue
        try:
            exact = ipaddress.ip_network(str(cidr), strict=False).num_addresses == 1
        except ValueError:
            exact = False
        return f"allows ipBlock {cidr}" + ("" if exact else " without excepting it")
    return None


def main(node=None):
    """Requires NetworkPolicy to keep pods away from the instance-metadata endpoint."""
    c = Check("metadata-egress-blocked", "Pods should not be able to reach the instance metadata endpoint", node=node)
    with c:
        workloads = c.get_node(".k8s.workloads")
        entries = [w.get_value() for w in workloads] if workloads.exists() else []
        if not entries:
            c.skip("No Kubernetes workloads found in this repository")

        ips = metadata_ips()
        policies_node = c.get_node(".k8s.network_policies")
        policies = [p.get_value() for p in policies_node] if policies_node.exists() else []
        # A pod's egress is restricted only by policies with Egress in policyTypes.
        egress_policies = [p for p in policies if "Egress" in (p.get("policy_types") or [])]

        def identity(w):
            return (w.get("kind"), w.get("namespace", "default"), w.get("name"))

        # A kustomize patch has no pod template labels; it is selected through
        # the labels of the definition it patches.
        labels_of = {}
        for w in entries:
            if w.get("pod_labels"):
                labels_of.setdefault(identity(w), w["pod_labels"])

        checked = 0
        for w in entries:
            if w.get("host_network") is True:
                continue  # NetworkPolicy doesn't reliably apply to hostNetwork pods; host-network reports them
            checked += 1
            namespace = w.get("namespace", "default")
            labels = w.get("pod_labels") or labels_of.get(identity(w), {})
            where = f"{w.get('path', '<unknown>')}: {w.get('kind')} {namespace}/{w.get('name', '<unknown>')}"

            selecting = [p for p in egress_policies
                         if p.get("namespace", "default") == namespace
                         and selector_matches(p.get("pod_selector") or {}, labels)]
            if not selecting:
                c.fail(f"{where} can reach {', '.join(map(str, ips))}: no NetworkPolicy selects it for egress")
                continue

            # Policies are additive, so one opening in any selecting policy is enough.
            for ip in ips:
                for policy in selecting:
                    why = next(filter(None, (opening(rule, ip) for rule in policy.get("egress") or [])), None)
                    if why:
                        c.fail(f"{where} can reach {ip}: NetworkPolicy {namespace}/{policy.get('name')} {why}")
                        break

        if not checked:
            c.skip("Every workload uses hostNetwork, which NetworkPolicy doesn't reliably cover (see host-network)")

    return c


if __name__ == "__main__":
    main()
