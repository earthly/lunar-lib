from lunar_policy import Check, variable_or_default
from helpers import parse_cpu_millicores, parse_mem_bytes


def main(node=None):
    """Ensures all containers have CPU and memory requests and limits."""
    c = Check("resources", "Containers should have CPU/memory requests and limits", node=node)
    with c:
        workloads = c.get_node(".k8s.workloads")
        if not workloads.exists():
            c.skip("No Kubernetes workloads found in this repository")
            return c

        try:
            max_ratio = float(variable_or_default("max_limit_to_request_ratio", "4"))
        except ValueError:
            max_ratio = 4.0

        for workload in workloads:
            kind = workload.get_value_or_default(".kind", "")
            name = workload.get_value_or_default(".name", "<unknown>")
            namespace = workload.get_value_or_default(".namespace", "default")
            path = workload.get_value_or_default(".path", "<unknown>")

            containers = workload.get_node(".containers")
            if not containers.exists():
                continue

            for container in containers:
                cname = container.get_value_or_default(".name", "<container>")
                prefix = f"{path}: {kind} {namespace}/{name} container {cname!r}"

                # Check for resources
                has_requests = container.get_value_or_default(".has_requests", False)
                has_limits = container.get_value_or_default(".has_limits", False)

                c.assert_true(has_requests, f"{prefix} missing resource requests")
                c.assert_true(has_limits, f"{prefix} missing resource limits")

                # Get actual values for ratio checks
                cpu_request = container.get_value_or_default(".cpu_request", None)
                cpu_limit = container.get_value_or_default(".cpu_limit", None)
                mem_request = container.get_value_or_default(".memory_request", None)
                mem_limit = container.get_value_or_default(".memory_limit", None)

                # Validate CPU ratio
                if cpu_request and cpu_limit:
                    r_cpu = parse_cpu_millicores(cpu_request)
                    l_cpu = parse_cpu_millicores(cpu_limit)
                    if r_cpu and l_cpu:
                        c.assert_true(
                            r_cpu <= l_cpu,
                            f"{prefix} has requests.cpu > limits.cpu ({cpu_request} > {cpu_limit})"
                        )
                        if max_ratio > 0 and r_cpu > 0:
                            c.assert_true(
                                l_cpu <= r_cpu * max_ratio,
                                f"{prefix} limits.cpu exceeds {max_ratio}x requests.cpu ({cpu_limit} vs {cpu_request})"
                            )

                # Validate memory ratio
                if mem_request and mem_limit:
                    r_mem = parse_mem_bytes(mem_request)
                    l_mem = parse_mem_bytes(mem_limit)
                    if r_mem and l_mem:
                        c.assert_true(
                            r_mem <= l_mem,
                            f"{prefix} has requests.memory > limits.memory ({mem_request} > {mem_limit})"
                        )
                        if max_ratio > 0 and r_mem > 0:
                            c.assert_true(
                                l_mem <= r_mem * max_ratio,
                                f"{prefix} limits.memory exceeds {max_ratio}x requests.memory ({mem_limit} vs {mem_request})"
                            )

    return c


if __name__ == "__main__":
    main()

