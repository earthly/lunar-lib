import math

from lunar_policy import Check

from helpers import (Findings, autoscalers_of, complete, entries, entries_or_skip, replica_range, same_release,
                     selector_matches)


def amount(value, total):
    """An IntOrString budget field as a pod count; percentages round up, as the disruption controller does."""
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            return math.ceil(float(text[:-1]) * total / 100)
        return int(text)
    return int(value)


def is_zero(value):
    return str(value).strip() in ("0", "0%")


def main(node=None):
    """Fails a PodDisruptionBudget that allows no voluntary disruption."""
    c = Check("pdb-budget", "PodDisruptionBudgets should allow at least one voluntary disruption", node=node)
    with c:
        pdbs = entries_or_skip(c, ".k8s.pdbs", "No PodDisruptionBudgets found in this repository")
        workloads = complete(entries(c, ".k8s.workloads"))
        hpas, scaled_objects = entries(c, ".k8s.hpas"), entries(c, ".k8s.scaled_objects")

        findings = Findings(c)
        for pdb in pdbs:
            what = f"PodDisruptionBudget {pdb.get('namespace', 'default')}/{pdb.get('name', '<unknown>')}"
            min_available, max_unavailable = pdb.get("min_available"), pdb.get("max_unavailable")
            selector = pdb.get("selector")

            findings.check(isinstance(selector, dict), pdb, f"{what} has no selector, so it covers no pods")
            if min_available is not None and max_unavailable is not None:
                findings.fail(pdb, f"{what} sets both minAvailable and maxUnavailable; set one")
                continue
            if max_unavailable is not None:
                findings.check(not is_zero(max_unavailable), pdb,
                               f"{what} allows no voluntary disruptions: maxUnavailable is {max_unavailable}")
                continue
            if min_available is None or not isinstance(selector, dict):
                continue

            covered = [w for w in workloads
                       if w.get("namespace", "default") == pdb.get("namespace", "default")
                       and same_release(pdb, w) and selector_matches(selector, w.get("pod_labels"))]
            if not covered:
                continue  # it covers nothing in this repository, so there's no size to compare with
            total = sum(replica_range(w, autoscalers_of(w, hpas, scaled_objects))[0] for w in covered)
            names = " and ".join(f"{w.get('kind')} {w.get('name')}" for w in covered)
            runs = "runs" if len(covered) == 1 else "run"
            together = "" if len(covered) == 1 else " together"
            try:
                desired = amount(min_available, total)
            except ValueError:
                continue  # not a count or a percentage; the API server rejects it
            findings.check(
                desired < total, pdb,
                f"{what} allows no voluntary disruptions: minAvailable {min_available} covers {names}, "
                f"which {runs} at least {total} replicas{together}"
            )
        findings.report(nothing_checked="No PodDisruptionBudgets found in this repository")

    return c


if __name__ == "__main__":
    main()
