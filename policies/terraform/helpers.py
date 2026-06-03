"""Extract Terraform-specific configuration from parsed HCL."""


def get_providers(native_files_node):
    """Extract provider version constraints from required_providers blocks.

    Returns: list of {name, version_constraint, is_pinned}
    """
    providers = {}
    if not native_files_node.exists():
        return []

    for f in native_files_node:
        hcl = f.get_node(".hcl")
        if not hcl.exists():
            continue
        raw = hcl.get_value()
        for tf_block in raw.get("terraform", []):
            if not isinstance(tf_block, dict):
                continue
            for rp_block in tf_block.get("required_providers", []):
                if not isinstance(rp_block, dict):
                    continue
                for name, config in rp_block.items():
                    version = None
                    if isinstance(config, dict):
                        version = config.get("version")
                    elif isinstance(config, str):
                        version = config
                    providers[name] = version

    return [
        {"name": name, "version_constraint": vc, "is_pinned": vc is not None}
        for name, vc in providers.items()
    ]


def get_modules(native_files_node):
    """Extract module sources and version pinning.

    Returns: list of {name, source, version, is_pinned}
    """
    modules = []
    if not native_files_node.exists():
        return []

    for f in native_files_node:
        hcl = f.get_node(".hcl")
        if not hcl.exists():
            continue
        raw = hcl.get_value()
        for mod_name, mod_configs in raw.get("module", {}).items():
            if not isinstance(mod_configs, list):
                continue
            for cfg in mod_configs:
                if not isinstance(cfg, dict):
                    continue
                source = cfg.get("source", "")
                version = cfg.get("version")
                is_pinned = version is not None or "?ref=" in source
                modules.append({
                    "name": mod_name,
                    "source": source,
                    "version": version,
                    "is_pinned": is_pinned,
                })
    return modules


def get_backend(native_files_node):
    """Extract backend configuration.

    Returns: {type, configured} or None
    """
    if not native_files_node.exists():
        return None

    for f in native_files_node:
        hcl = f.get_node(".hcl")
        if not hcl.exists():
            continue
        raw = hcl.get_value()
        for tf_block in raw.get("terraform", []):
            if not isinstance(tf_block, dict):
                continue
            backends = tf_block.get("backend", [])
            if isinstance(backends, list):
                for backend in backends:
                    if isinstance(backend, dict):
                        for backend_type in backend:
                            return {"type": backend_type, "configured": True}
            elif isinstance(backends, dict):
                for backend_type in backends:
                    return {"type": backend_type, "configured": True}
    return None


# ---------------------------------------------------------------------------
# AWS resource traversal — shared by the SOC 2 AWS checks.
#
# hcl2json shape: raw["resource"][<type>][<name>] -> [ { ...attrs... } ]
# Nested blocks (ingress, access_logs, ...) are likewise [ {..} ] (or a bare
# {..}). References like `bucket = aws_s3_bucket.logs.id` render as the string
# "${aws_s3_bucket.logs.id}". These helpers normalize those quirks.
# ---------------------------------------------------------------------------


def as_blocks(value):
    """Normalize an hcl2json body/block to a list of dicts.

    A resource body is ``[ {..} ]``; a nested block may be ``[ {..} ]`` or a
    bare ``{..}``. Anything else yields an empty list.
    """
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def iter_resources(native_files_node, *rtypes):
    """Yield ``(rtype, name, config)`` for every resource of the given types.

    With no ``rtypes`` it yields every resource. Each ``config`` is a dict of
    one resource instance's attributes/blocks.
    """
    if not native_files_node.exists():
        return
    want = set(rtypes)
    for f in native_files_node:
        hcl = f.get_node(".hcl")
        if not hcl.exists():
            continue
        raw = hcl.get_value()
        if not isinstance(raw, dict):
            continue
        resources = raw.get("resource", {})
        if not isinstance(resources, dict):
            continue
        for rtype, named in resources.items():
            if want and rtype not in want:
                continue
            if not isinstance(named, dict):
                continue
            for name, configs in named.items():
                for cfg in as_blocks(configs):
                    yield rtype, name, cfg


def has_resource(native_files_node, *rtypes):
    """True if at least one resource of the given types is present."""
    for _ in iter_resources(native_files_node, *rtypes):
        return True
    return False


def block(cfg, key):
    """Return nested block(s) under ``key`` as a list of dicts."""
    return as_blocks(cfg.get(key))


def references(value, rtype, name=None):
    """True if an hcl2json value references ``rtype`` (optionally ``.name``).

    Handles interpolation strings (``"${aws_s3_bucket.logs.id}"``) and lists of
    them. With ``name`` omitted, matches any reference to the type.
    """
    needle = "{}.{}".format(rtype, name) if name else rtype
    if isinstance(value, list):
        return any(references(v, rtype, name) for v in value)
    return isinstance(value, str) and needle in value


def as_int(value):
    """Coerce an hcl2json numeric (int or stringified) to int, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def truthy(value):
    """Interpret an hcl2json scalar as a boolean (handles "true"/"false")."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


_WORLD_V4 = "0.0.0.0/0"
_WORLD_V6 = "::/0"


def _open_to_world(rule):
    """True if a rule's CIDR fields include 0.0.0.0/0 or ::/0."""
    for key in ("cidr_blocks", "ipv6_cidr_blocks"):
        vals = rule.get(key)
        if isinstance(vals, list) and (_WORLD_V4 in vals or _WORLD_V6 in vals):
            return True
    # aws_vpc_security_group_ingress_rule uses scalar cidr_ipv4 / cidr_ipv6
    return rule.get("cidr_ipv4") == _WORLD_V4 or rule.get("cidr_ipv6") == _WORLD_V6


def _covers_port(rule, port):
    """True if a rule's protocol/port range covers ``port``."""
    proto = str(rule.get("protocol", rule.get("ip_protocol", ""))).lower()
    if proto in ("-1", "all"):
        return True
    frm = as_int(rule.get("from_port"))
    to = as_int(rule.get("to_port"))
    if frm is None or to is None:
        return False
    return frm <= port <= to


def public_ingress_offenders(native_files_node, port):
    """Return labels of ingress rules that expose ``port`` to the whole internet.

    Inspects inline ``aws_security_group`` ingress blocks, standalone
    ``aws_security_group_rule`` (type=ingress), and
    ``aws_vpc_security_group_ingress_rule`` resources.
    """
    offenders = []

    for _, name, cfg in iter_resources(native_files_node, "aws_security_group"):
        for ing in block(cfg, "ingress"):
            if _open_to_world(ing) and _covers_port(ing, port):
                offenders.append("aws_security_group.{}".format(name))
                break

    for _, name, cfg in iter_resources(native_files_node, "aws_security_group_rule"):
        if str(cfg.get("type", "")).lower() != "ingress":
            continue
        if _open_to_world(cfg) and _covers_port(cfg, port):
            offenders.append("aws_security_group_rule.{}".format(name))

    for _, name, cfg in iter_resources(native_files_node, "aws_vpc_security_group_ingress_rule"):
        if _open_to_world(cfg) and _covers_port(cfg, port):
            offenders.append("aws_vpc_security_group_ingress_rule.{}".format(name))

    return offenders


def has_any_security_group(native_files_node):
    """True if the config declares any security group or ingress-rule resource."""
    return has_resource(
        native_files_node,
        "aws_security_group",
        "aws_security_group_rule",
        "aws_vpc_security_group_ingress_rule",
    )
