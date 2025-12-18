from lunar_policy import Check, variable_or_default
import re
from typing import Optional

WORKLOAD_KINDS = {
    "Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "Pod",
}

def check_resources_requirements():
    """
    Policy:
      - For each container (incl. initContainers) in common workload kinds,
        ensure requests.cpu, requests.memory, limits.cpu, limits.memory exist.
      - Ensure requests <= limits for both CPU and memory.
      - Optionally cap limit:request ratio (default 4x).

    Inputs (all optional):
      - maxLimitToRequestRatio: integer/float as string, e.g. "4" (default "4")
    """
    with Check("k8s-resources", "Containers have CPU/Memory requests & limits") as c:
        descriptors = c.get_node(".k8s.descriptors")
        if not descriptors.exists():
            return
        require_requests = _bool(variable_or_default("requireRequests", "true"), True)
        require_limits   = _bool(variable_or_default("requireLimits",   "true"), True)
        try:
            max_ratio = float(variable_or_default("maxLimitToRequestRatio", "4"))
        except ValueError:
            max_ratio = 4.0

        for desc in descriptors:
            if not desc.get_value_or_default(".valid", False):
                continue

            obj = desc.get_node(".contents")
            if not obj.exists():
                continue
            
            kind = obj.get_value(".kind")
            if kind not in WORKLOAD_KINDS:
                continue

            meta = obj.get_node(".metadata")
            ns = meta.get_value_or_default(".namespace", "default")
            name = meta.get_value_or_default(".name", "<noname>")
            fname = desc.get_value_or_default(".k8s_file_location", "<file>")

            spec = _template_spec(obj)
            for container in _all_containers(spec):
                cname = container.get("name") or "<container>"
                resources = container.get("resources") or {}
                req = resources.get("requests") or {}
                lim = resources.get("limits") or {}

                # Presence checks
                c.assert_true("cpu" in req,
                    f"{fname}: {kind} {ns}/{name} container {cname!r} missing resources.requests.cpu")
                c.assert_true("memory" in req,
                    f"{fname}: {kind} {ns}/{name} container {cname!r} missing resources.requests.memory")
                c.assert_true("cpu" in lim,
                    f"{fname}: {kind} {ns}/{name} container {cname!r} missing resources.limits.cpu")
                c.assert_true("memory" in lim,
                    f"{fname}: {kind} {ns}/{name} container {cname!r} missing resources.limits.memory")

                # Numeric + ordering checks (only if both sides present)
                r_cpu = _parse_cpu_millicores(req.get("cpu"))
                l_cpu = _parse_cpu_millicores(lim.get("cpu"))
                r_mem = _parse_mem_bytes(req.get("memory"))
                l_mem = _parse_mem_bytes(lim.get("memory"))

                if req.get("cpu") is not None:
                    c.assert_true(r_cpu is not None, f"{fname}: {kind} {ns}/{name} container {cname!r} has invalid requests.cpu={req.get('cpu')!r}")
                if lim.get("cpu") is not None:
                    c.assert_true(l_cpu is not None, f"{fname}: {kind} {ns}/{name} container {cname!r} has invalid limits.cpu={lim.get('cpu')!r}")

                if req.get("memory") is not None:
                    c.assert_true(r_mem is not None, f"{fname}: {kind} {ns}/{name} container {cname!r} has invalid requests.memory={req.get('memory')!r}")
                if lim.get("memory") is not None:
                    c.assert_true(l_mem is not None, f"{fname}: {kind} {ns}/{name} container {cname!r} has invalid limits.memory={lim.get('memory')!r}")

                # Ratio checks
                if r_cpu is not None and l_cpu is not None:
                    c.assert_true(r_cpu <= l_cpu, f"{fname}: {kind} {ns}/{name} container {cname!r} has requests.cpu > limits.cpu ({req.get('cpu')} > {lim.get('cpu')})")
                    if max_ratio > 0:
                        c.assert_true(l_cpu <= r_cpu * max_ratio, f"{fname}: {kind} {ns}/{name} container {cname!r} limits.cpu > {max_ratio}x requests.cpu ({lim.get('cpu')} vs {req.get('cpu')})")

                if r_mem is not None and l_mem is not None:
                    c.assert_true(r_mem <= l_mem, f"{fname}: {kind} {ns}/{name} container {cname!r} has requests.memory > limits.memory ({req.get('memory')} > {lim.get('memory')})")
                    if max_ratio > 0:
                        c.assert_true(l_mem <= r_mem * max_ratio, f"{fname}: {kind} {ns}/{name} container {cname!r} limits.memory > {max_ratio}x requests.memory ({lim.get('memory')} vs {req.get('memory')})")


def _bool(v: str, default: bool) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

def _template_spec(obj):
    """Given a node representing a k8s object, return the pod template spec node."""
    kind = obj.get_value(".kind")
    if kind == "CronJob":
        return obj.get_node(".spec.jobTemplate.spec.template.spec")
    if kind == "Pod":
        return obj.get_node(".spec")
    # Deployment/StatefulSet/DaemonSet/Job
    return obj.get_node(".spec.template.spec")

def _all_containers(spec_node):
    """Given a pod spec node, return all containers (regular + init)."""
    containers = spec_node.get_value_or_default(".containers", [])
    init_containers = spec_node.get_value_or_default(".initContainers", [])
    return containers + init_containers

def _parse_cpu_millicores(v) -> Optional[float]:
    """Return CPU in millicores, or None if unparsable."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) * 1000.0  # cores -> mCPU
    s = str(v).strip()
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([num]?)", s)
    if not m:
        return None
    val = float(m.group(1))
    suf = m.group(2)
    if suf == "n":   # nano-cores
        return val / 1_000_000.0
    if suf == "u":   # micro-cores
        return val / 1_000.0
    if suf == "m":   # millicores
        return val
    return val * 1000.0  # cores -> mCPU

_BIN = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4, "Pi": 1024**5, "Ei": 1024**6}
_DEC = {"K": 1000, "M": 1000**2, "G": 1000**3, "T": 1000**4, "P": 1000**5, "E": 1000**6}

def _parse_mem_bytes(v) -> Optional[float]:
    """Return memory in bytes, or None if unparsable."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([KMGTP]i|[KMGTPE])?B?", s)
    if not m:
        return None
    val = float(m.group(1))
    suf = m.group(2)
    if not suf:
        return val
    if suf in _BIN:
        return val * _BIN[suf]
    if suf in _DEC:
        return val * _DEC[suf]
    return None
