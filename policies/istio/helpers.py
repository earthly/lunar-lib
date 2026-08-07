"""Shared helpers for the Istio policy checks."""


def mesh_present(c):
    """Gate an Istio check on the `.mesh` category, driving the pending lifecycle.

    Accessing `.mesh` via ``get_node().exists()`` registers this check's
    dependency on the istio collector and lets the hub resolve the check
    correctly instead of skipping before the collector has run:

    * While collectors are still running and `.mesh` is absent, the underlying
      ``get_value`` raises ``NoDataError``, which the ``Check`` context manager
      turns into **PENDING** — the check re-evaluates on the next cycle rather
      than resolving early.
    * Only once workflows have finished with no `.mesh` does ``.exists()``
      return ``False`` and we resolve to a terminal **SKIP** (this is a
      vendor-specific policy: no mesh means it doesn't apply).
    * When `.mesh` is present, returns ``True`` and the caller proceeds to its
      assertions (→ pass/fail).

    Returns ``True`` when `.mesh` is present; otherwise calls ``c.skip(...)``
    (which raises ``SkippedError``) and never returns.
    """
    if not c.get_node(".mesh").exists():
        c.skip("No service-mesh (.mesh) data on this component — istio not in use")
    return True
