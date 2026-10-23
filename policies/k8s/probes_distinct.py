from lunar_policy import Check

from helpers import Findings, describe, entries_or_skip, require_fields


def target(probe):
    """What a probe checks, comparable across probes; None when it can't be told."""
    handler = probe.get("handler")
    if handler == "httpGet":
        return f"httpGet :{probe.get('port')}{probe.get('path') or '/'}"
    if handler in ("tcpSocket", "grpc"):
        service = f" service {probe.get('service')}" if probe.get("service") else ""
        return f"{handler} :{probe.get('port')}{service}"
    if handler == "exec":
        return "exec " + " ".join(str(part) for part in probe.get("command") or [])
    return None


def main(node=None):
    """Requires each container's liveness and readiness probes to check different endpoints."""
    c = Check("probes-distinct", "Liveness and readiness probes should check different endpoints", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")
        containers = [(w, ct) for w in workloads if w.get("kind") not in ("Job", "CronJob")
                      for ct in (w.get("containers") or []) + (w.get("init_containers") or [])]
        require_fields(c, [ct for _, ct in containers], ["liveness_probe", "readiness_probe"], "probe details")

        findings = Findings(c)
        for w, ct in containers:
            liveness, readiness = ct.get("liveness_probe"), ct.get("readiness_probe")
            if not liveness or not readiness:
                continue  # the probes check reports a missing probe
            checks = target(liveness)
            findings.check(
                checks is None or checks != target(readiness), w,
                f"{describe(w)} container {ct.get('name', '<container>')!r} livenessProbe and readinessProbe both check {checks}"
            )
        findings.report(nothing_checked="No container has both a liveness and a readiness probe")

    return c


if __name__ == "__main__":
    main()
