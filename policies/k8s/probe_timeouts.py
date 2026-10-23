from lunar_policy import Check

from helpers import Findings, describe, entries_or_skip, int_input, require_fields

PROBES = (("liveness_probe", "livenessProbe"), ("readiness_probe", "readinessProbe"), ("startup_probe", "startupProbe"))


def main(node=None):
    """Requires probe timeouts of at least min_probe_timeout_seconds and below the probe period."""
    c = Check("probe-timeouts", "Probe timeouts should be long enough and shorter than the probe period", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")
        containers = [(w, ct) for w in workloads
                      for ct in (w.get("containers") or []) + (w.get("init_containers") or [])]
        require_fields(c, [ct for _, ct in containers], [field for field, _ in PROBES], "probe details")

        min_timeout = int_input("min_probe_timeout_seconds", 1)
        findings = Findings(c)
        for w, ct in containers:
            prefix = f"{describe(w)} container {ct.get('name', '<container>')!r}"
            for field, label in PROBES:
                probe = ct.get(field)
                if not probe:
                    continue
                timeout, period = probe.get("timeout_seconds") or 1, probe.get("period_seconds") or 10
                findings.check(timeout >= min_timeout, w, f"{prefix} {label} timeoutSeconds {timeout} is below {min_timeout}")
                findings.check(timeout < period, w,
                               f"{prefix} {label} timeoutSeconds {timeout} is not below periodSeconds {period}")
        findings.report(nothing_checked="No probes found in this repository")

    return c


if __name__ == "__main__":
    main()
