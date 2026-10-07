"""Helper functions for K8s policy checks."""

import re
from typing import Optional


# Binary suffixes (powers of 1024)
_BIN_SUFFIXES = {
    "Ki": 1024,
    "Mi": 1024**2,
    "Gi": 1024**3,
    "Ti": 1024**4,
    "Pi": 1024**5,
    "Ei": 1024**6,
}

# Decimal suffixes (powers of 1000)
_DEC_SUFFIXES = {
    "K": 1000,
    "M": 1000**2,
    "G": 1000**3,
    "T": 1000**4,
    "P": 1000**5,
    "E": 1000**6,
}


def parse_cpu_millicores(value) -> Optional[float]:
    """
    Parse a Kubernetes CPU value and return millicores.

    Examples:
        "100m" -> 100.0
        "0.5" -> 500.0
        "1" -> 1000.0
        "500n" -> 0.0005

    Returns None if the value cannot be parsed.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value) * 1000.0  # cores -> millicores

    s = str(value).strip()
    match = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([num]?)", s)
    if not match:
        return None

    val = float(match.group(1))
    suffix = match.group(2)

    if suffix == "n":  # nanocores
        return val / 1_000_000.0
    if suffix == "u":  # microcores
        return val / 1_000.0
    if suffix == "m":  # millicores
        return val
    # No suffix = cores
    return val * 1000.0


def parse_mem_bytes(value) -> Optional[float]:
    """
    Parse a Kubernetes memory value and return bytes.

    Examples:
        "128Mi" -> 134217728.0
        "1Gi" -> 1073741824.0
        "500M" -> 500000000.0

    Returns None if the value cannot be parsed.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    match = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([KMGTPE]i|[KMGTPE])?B?", s)
    if not match:
        return None

    val = float(match.group(1))
    suffix = match.group(2)

    if not suffix:
        return val

    if suffix in _BIN_SUFFIXES:
        return val * _BIN_SUFFIXES[suffix]

    if suffix in _DEC_SUFFIXES:
        return val * _DEC_SUFFIXES[suffix]

    return None


def selector_matches(selector, labels):
    """Kubernetes LabelSelector semantics: matchLabels is an AND of equalities,
    matchExpressions supports In / NotIn / Exists / DoesNotExist, an empty
    selector matches every pod in the namespace, and a null selector matches
    none (as a policy/v1 PodDisruptionBudget applies it)."""
    if not isinstance(selector, dict):
        return False
    labels = {str(k): str(v) for k, v in (labels or {}).items()}
    for key, value in (selector.get("matchLabels") or {}).items():
        if labels.get(str(key)) != str(value):
            return False
    for expr in selector.get("matchExpressions") or []:
        key = str(expr.get("key", ""))
        values = {str(v) for v in (expr.get("values") or [])}
        operator = expr.get("operator")
        if operator == "In":
            ok = key in labels and labels[key] in values
        elif operator == "NotIn":
            ok = key not in labels or labels[key] not in values
        elif operator == "Exists":
            ok = key in labels
        elif operator == "DoesNotExist":
            ok = key not in labels
        else:
            ok = False  # the API server rejects any other operator
        if not ok:
            return False
    return True


# Rendered Helm charts -------------------------------------------------------

def values_label(obj):
    """The values set an entry was rendered with, minus the chart's own
    values.yaml when overlays follow it; "" for a plain manifest."""
    render = obj.get("render") if isinstance(obj, dict) else None
    if not render:
        return ""
    values = list(render.get("values") or [])
    if len(values) > 1 and values[0] == "values.yaml":
        values = values[1:]
    return " ".join(values)


def where(obj):
    """Where a finding is: the file, plus the values set for a chart render."""
    path = obj.get("path") or "<unknown>"
    label = values_label(obj)
    return f"{path} [{label}]" if label else path


def same_release(a, b):
    """Whether two entries can be deployed together. The values sets of one
    chart are alternative deployments of the same release, so they never are;
    plain manifests and other charts always can be."""
    ra, rb = a.get("render"), b.get("render")
    if not ra or not rb or ra.get("chart") != rb.get("chart"):
        return True
    return list(ra.get("values") or []) == list(rb.get("values") or [])


class Findings:
    """Collects a check's verdicts so that a finding repeated across the values
    sets of one chart is reported once, naming each set it shows up in."""

    def __init__(self, check):
        self._check = check
        self._failed = {}
        self._passed = {}

    def check(self, ok, obj, message):
        key = (obj.get("path") or "<unknown>", message)
        bucket = self._passed if ok else self._failed
        labels = bucket.setdefault(key, [])
        label = values_label(obj)
        if label and label not in labels:
            labels.append(label)

    def fail(self, obj, message):
        self.check(False, obj, message)

    def report(self, nothing_checked=None):
        """Records the verdicts. With nothing_checked, a check that recorded
        none skips with that reason rather than passing on nothing."""
        if nothing_checked and not self._failed and not self._passed:
            self._check.skip(NO_VALUES_SET if only_unchecked_charts(self._check) else nothing_checked)
        for (path, message), labels in self._failed.items():
            place = f"{path} [{', '.join(labels)}]" if labels else path
            self._check.fail(f"{place}: {message}")
        for key in self._passed:
            if key not in self._failed:
                self._check.assert_true(True, f"{key[0]}: {key[1]}")


def only_unchecked_charts(c):
    """Whether the component's only Kubernetes content is Helm charts that no
    values set applies to. Call only after collection has finished."""
    manifests = c.get_node(".k8s.manifests")
    entries = [m.get_value() for m in manifests] if manifests.exists() else []
    return bool(entries) and all((m.get("render") or {}).get("validated_only") is True for m in entries)


NO_VALUES_SET = ("No values set applies to the Helm charts here, so only `valid` checks them. "
                 "List the values files you deploy in the k8s collector's helm_values, or set helm_values_chains")


def entries_or_skip(c, path, reason):
    """The entries at path, skipping when there are none; pending while collection runs."""
    node = c.get_node(path)
    entries = [e.get_value() for e in node] if node.exists() else []
    if not entries:
        c.skip(NO_VALUES_SET if only_unchecked_charts(c) else reason)
    return entries


def require_fields(c, entries, fields, what):
    """Skips a check when the k8s collector predates the fields it reads."""
    for entry in entries:
        missing = [f for f in fields if f not in entry]
        if missing:
            c.skip(f"The k8s collector predates {what} ({', '.join(missing)}); update it to run this check")


def identity(workload):
    return (workload.get("kind"), workload.get("namespace", "default"), workload.get("name"))


def autoscalers_of(workload, hpas, scaled_objects):
    """The HPAs and KEDA ScaledObjects that scale a workload, by scaleTargetRef
    in its namespace, never from another values set of its own chart."""
    kind, namespace, name = identity(workload)
    found = []
    for label, entries in (("HorizontalPodAutoscaler", hpas), ("ScaledObject", scaled_objects)):
        for a in entries:
            if (a.get("namespace", "default") == namespace and a.get("target_workload") == name
                    and a.get("target_kind") in (None, kind) and same_release(workload, a)):
                found.append((label, a))
    return found


def replica_range(workload, autoscalers):
    """(smallest, largest) number of pods: the autoscaler's range when one
    scales the workload (a minimum of at least 1), else spec.replicas."""
    if autoscalers:
        smallest = min(max(int(a.get("min_replicas") or 0), 1) for _, a in autoscalers)
        largest = max(int(a.get("max_replicas") or 0) for _, a in autoscalers)
        return smallest, max(largest, smallest)
    replicas = workload.get("replicas")
    replicas = 1 if replicas is None else int(replicas)
    return replicas, replicas


def resolve_labels(workloads):
    """Pod template labels per workload identity. A kustomize patch has none of
    its own, so it is matched through the labels of the definition it patches."""
    labels = {}
    for w in workloads:
        if w.get("pod_labels"):
            labels.setdefault(identity(w), w["pod_labels"])
    return labels


def entries(c, path):
    """The entries at an optional path; pending while collection runs."""
    node = c.get_node(path)
    return [e.get_value() for e in node] if node.exists() else []


def complete(workloads):
    """Workloads with pod template labels. apps/v1 requires them, so an entry
    without any is a partial manifest such as a kustomize patch."""
    return [w for w in workloads if w.get("pod_labels")]


def list_input(name, default=""):
    """A comma- or whitespace-separated input."""
    from lunar_policy import variable_or_default
    raw = variable_or_default(name, default) or ""
    return [item for item in raw.replace(",", " ").split() if item]


def int_input(name, default):
    from lunar_policy import variable_or_default
    raw = variable_or_default(name, str(default))
    try:
        return int(str(raw).strip())
    except ValueError:
        raise ValueError(f"Policy misconfiguration: {name} must be an integer, got {raw!r}")


def describe(workload):
    return f"{workload.get('kind')} {workload.get('namespace', 'default')}/{workload.get('name', '<unknown>')}"
