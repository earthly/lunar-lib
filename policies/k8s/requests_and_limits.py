from lunar_policy import Check, variable_or_default
from helpers import Findings, entries_or_skip, parse_cpu_millicores, parse_mem_bytes


def main(node=None):
    """Ensures all containers have CPU and memory requests and limits."""
    c = Check("requests-and-limits", "Containers should have CPU/memory requests and limits", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")

        try:
            max_ratio = float(variable_or_default("max_limit_to_request_ratio", "4"))
        except ValueError:
            max_ratio = 4.0

        findings = Findings(c)
        for workload in workloads:
            kind = workload.get("kind", "")
            name = workload.get("name", "<unknown>")
            namespace = workload.get("namespace", "default")

            for container in workload.get("containers") or []:
                cname = container.get("name", "<container>")
                prefix = f"{kind} {namespace}/{name} container {cname!r}"

                # Check for resources
                findings.check(container.get("has_requests") is True, workload, f"{prefix} missing resource requests")
                findings.check(container.get("has_limits") is True, workload, f"{prefix} missing resource limits")

                # Get actual values for ratio checks
                cpu_request = container.get("cpu_request")
                cpu_limit = container.get("cpu_limit")
                mem_request = container.get("memory_request")
                mem_limit = container.get("memory_limit")

                # Validate CPU ratio
                if cpu_request is not None and cpu_limit is not None:
                    r_cpu = parse_cpu_millicores(cpu_request)
                    l_cpu = parse_cpu_millicores(cpu_limit)
                    if r_cpu is not None and l_cpu is not None:
                        findings.check(
                            r_cpu <= l_cpu, workload,
                            f"{prefix} has requests.cpu > limits.cpu ({cpu_request} > {cpu_limit})"
                        )
                        if max_ratio > 0 and r_cpu > 0:
                            findings.check(
                                l_cpu <= r_cpu * max_ratio, workload,
                                f"{prefix} limits.cpu exceeds {max_ratio}x requests.cpu ({cpu_limit} vs {cpu_request})"
                            )

                # Validate memory ratio
                if mem_request is not None and mem_limit is not None:
                    r_mem = parse_mem_bytes(mem_request)
                    l_mem = parse_mem_bytes(mem_limit)
                    if r_mem is not None and l_mem is not None:
                        findings.check(
                            r_mem <= l_mem, workload,
                            f"{prefix} has requests.memory > limits.memory ({mem_request} > {mem_limit})"
                        )
                        if max_ratio > 0 and r_mem > 0:
                            findings.check(
                                l_mem <= r_mem * max_ratio, workload,
                                f"{prefix} limits.memory exceeds {max_ratio}x requests.memory ({mem_limit} vs {mem_request})"
                            )
        findings.report()

    return c


if __name__ == "__main__":
    main()

