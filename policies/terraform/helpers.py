"""Extract Terraform-specific configuration from parsed HCL."""

import posixpath
import re


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


def _split_module_source(source):
    """Split a module ``source`` into ``(path, subdir)``, lowercased.

    Drops any ``?query`` (e.g. ``?ref=v1.2.0``) and splits off a ``//subdir``
    (``terraform-aws-modules/eks/aws//modules/karpenter``). The ``//`` of a
    ``scheme://`` prefix is not taken for a subdir separator.
    """
    src = str(source).split("?", 1)[0].strip().lower()
    scheme = src.find("://")
    sep = src.find("//", scheme + 3 if scheme >= 0 else 0)
    if sep < 0:
        return src.strip("/"), ""
    return src[:sep].strip("/"), src[sep + 2:].strip("/")


def module_source_matches(source, wanted):
    """True if a module ``source`` calls the registry module ``wanted``.

    ``wanted`` is ``<namespace>/<name>/<provider>``, optionally with a
    ``//<subdir>``. Matches whole path segments, so
    ``terraform-aws-modules/eks/aws`` does not match
    ``terraform-aws-modules/eks-pod-identity/aws``; a registry host prefix
    (``registry.terraform.io/...``) is allowed. A submodule call
    (``.../eks/aws//modules/karpenter``) matches only when ``wanted`` names
    that same subdir.
    """
    src_path, src_sub = _split_module_source(source)
    want_path, want_sub = _split_module_source(wanted)
    want_segs = want_path.split("/")
    return src_sub == want_sub and src_path.split("/")[-len(want_segs):] == want_segs


def iter_module_calls(native_files_node, *sources):
    """Yield ``(name, config)`` for ``module`` blocks calling one of ``sources``.

    Each source is a registry module path matched by
    ``module_source_matches``. With no sources, yields every module call. Used
    so checks can evaluate module-provisioned infrastructure (e.g.
    ``terraform-aws-modules/eks/aws``) by reading the module's input arguments,
    rather than skipping because the underlying ``aws_*`` resource lives inside
    the module and isn't in the HCL.
    """
    if not native_files_node.exists():
        return
    for f in native_files_node:
        hcl = f.get_node(".hcl")
        if not hcl.exists():
            continue
        raw = hcl.get_value()
        if not isinstance(raw, dict):
            continue
        modules = raw.get("module")
        if not isinstance(modules, dict):
            continue
        for mname, configs in modules.items():
            for cfg in as_blocks(configs):
                src = cfg.get("source", "")
                if not sources or any(module_source_matches(src, s) for s in sources):
                    yield mname, cfg


# Registry modules that provision an RDS instance or cluster and take the
# instance arguments (storage_encrypted, publicly_accessible,
# enabled_cloudwatch_logs_exports) directly. Not the rds submodules for
# parameter/option/subnet groups, which create no database.
RDS_MODULE_SOURCES = (
    "terraform-aws-modules/rds/aws",
    "terraform-aws-modules/rds/aws//modules/db_instance",
    "terraform-aws-modules/rds-aurora/aws",
)


def first_set(cfg, keys, default=None):
    """Return ``(key, value)`` for the first of ``keys`` set (non-null) in ``cfg``.

    For module arguments renamed across major versions, e.g.
    terraform-aws-modules/eks v21 dropping the ``cluster_`` prefix. Returns
    ``(None, default)`` when none is set.
    """
    for k in keys:
        if cfg.get(k) is not None:
            return k, cfg[k]
    return None, default


def block(cfg, key):
    """Return nested block(s) under ``key`` as a list of dicts."""
    return as_blocks(cfg.get(key))


def references(value, rtype, name=None):
    """True if an hcl2json value references ``rtype`` (optionally ``.name``).

    Handles interpolation strings (``"${aws_s3_bucket.logs.id}"``) and lists of
    them. With ``name`` omitted, matches any reference to the type.

    Matches on whole address segments so ``aws_lb.web`` does NOT match
    ``${aws_lb.web2.arn}`` — a resource reference always carries a trailing
    attribute/index, or is the bare address itself.
    """
    if isinstance(value, list):
        return any(references(v, rtype, name) for v in value)
    if not isinstance(value, str):
        return False
    if name is None:
        return "{}.".format(rtype) in value or "{}[".format(rtype) in value
    target = "{}.{}".format(rtype, name)
    return (
        (target + ".") in value      # ${aws_lb.web.arn}
        or (target + "[") in value   # ${aws_lb.web[0].arn}
        or value.strip("${} \t") == target  # bare ${aws_lb.web}
    )


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


def public_ingress_offenders_for_ports(native_files_node, ports):
    """Map each of ``ports`` to the SG labels that expose it to the whole internet.

    Single traversal over all three security-group shapes (inline
    ``aws_security_group`` ingress blocks, standalone ``aws_security_group_rule``
    ingress, and ``aws_vpc_security_group_ingress_rule``). Returns
    ``{port: [labels]}`` containing only ports with at least one offender.
    A protocol "-1"/"all" world-open rule matches every port (it genuinely
    exposes all of them).
    """
    result = {p: [] for p in ports}

    def scan(label, rule):
        if not _open_to_world(rule):
            return
        for p in ports:
            if _covers_port(rule, p) and label not in result[p]:
                result[p].append(label)

    for _, name, cfg in iter_resources(native_files_node, "aws_security_group"):
        for ing in block(cfg, "ingress"):
            scan("aws_security_group.{}".format(name), ing)

    for _, name, cfg in iter_resources(native_files_node, "aws_security_group_rule"):
        if str(cfg.get("type", "")).lower() == "ingress":
            scan("aws_security_group_rule.{}".format(name), cfg)

    for _, name, cfg in iter_resources(native_files_node, "aws_vpc_security_group_ingress_rule"):
        scan("aws_vpc_security_group_ingress_rule.{}".format(name), cfg)

    return {p: labels for p, labels in result.items() if labels}


def has_any_security_group(native_files_node):
    """True if the config declares any security group or ingress-rule resource."""
    return has_resource(
        native_files_node,
        "aws_security_group",
        "aws_security_group_rule",
        "aws_vpc_security_group_ingress_rule",
    )


# ---------------------------------------------------------------------------
# AWS Load Balancer Controller ALBs.
#
# The controller builds an ALB from each Kubernetes Ingress it manages, and
# Ingresses sharing alb.ingress.kubernetes.io/group.name share one ALB. When
# Terraform declares those Ingresses (kubernetes_ingress_v1 /
# kubernetes_ingress), the ALB's scheme, WAF and attributes are annotations
# rather than aws_lb arguments. Annotations written as an expression are
# evaluated statically where possible; anything else is unknown, and an unknown
# value never fails a check.
# ---------------------------------------------------------------------------

LBC_PREFIX = "alb.ingress.kubernetes.io/"
INGRESS_TYPES = ("kubernetes_ingress_v1", "kubernetes_ingress")


class _Unknown(object):
    def __repr__(self):
        return "UNKNOWN"


UNKNOWN = _Unknown()  # an annotation value that can't be evaluated statically

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
# After a quoted map value: the next item, or the end of the map. Anything else
# (an operator) means the value is a larger expression.
_VALUE_END = set(",}\"_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r"}


def _literal(value):
    """An hcl2json map value as a string, or UNKNOWN for an expression."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and "${" not in value and "%{" not in value:
        return value
    return UNKNOWN


def _literal_map(value):
    """``(values, complete)`` for an hcl2json map literal, else None."""
    if isinstance(value, dict):
        return {k: _literal(v) for k, v in value.items()}, True
    return None


class _MapExpr(object):
    """Evaluate the expression text hcl2json keeps for a non-literal map.

    Understands map literals, ``local.<name>`` (one level, map-literal locals
    only) and ``merge(...)`` of those. ``evaluate`` returns ``(values,
    complete)``: ``values`` maps each key to a string or UNKNOWN, and
    ``complete`` is False when the map may hold keys not listed. Returns None
    when the expression isn't a map it can read.
    """

    def __init__(self, text, local_maps):
        self.s, self.i, self.locals = text, 0, local_maps

    def evaluate(self):
        result = self._expr()
        return result if self._peek() == "" else None

    def _skip_space(self):
        s = self.s
        while self.i < len(s):
            if s[self.i].isspace():
                self.i += 1
            elif s[self.i] == "#" or s.startswith("//", self.i):
                nl = s.find("\n", self.i)
                self.i = len(s) if nl < 0 else nl
            elif s.startswith("/*", self.i):
                end = s.find("*/", self.i + 2)
                self.i = len(s) if end < 0 else end + 2
            else:
                return

    def _peek(self):
        self._skip_space()
        return self.s[self.i] if self.i < len(self.s) else ""

    def _string(self):
        """Read a quoted string; return ``(text, is_template)``."""
        s, j, out, template = self.s, self.i + 1, [], False
        while j < len(s) and s[j] != '"':
            if s[j] == "\\" and j + 1 < len(s):
                esc = _ESCAPES.get(s[j + 1])
                template = template or esc is None
                out.append(esc or "")
                j += 2
            elif s.startswith("${", j) or s.startswith("%{", j):
                template = True
                j = self._skip_interpolation(j)
            else:
                out.append(s[j])
                j += 1
        self.i = j + 1
        return "".join(out), template

    def _skip_interpolation(self, j):
        """Index just past the ``${...}`` starting at ``j``, nested strings included."""
        s, depth = self.s, 0
        while j < len(s):
            if s[j] == '"':
                self.i = j
                self._string()
                j = self.i
                continue
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        return j

    def _skip_expr(self):
        """Skip an expression this evaluator doesn't read."""
        s, depth = self.s, 0
        while self.i < len(s):
            c = s[self.i]
            if c == '"':
                self._string()
                continue
            if c == "#" or s.startswith("//", self.i):
                nl = s.find("\n", self.i)  # stop AT the newline: it may end the value
                self.i = len(s) if nl < 0 else nl
                continue
            if s.startswith("/*", self.i):
                end = s.find("*/", self.i + 2)
                self.i = len(s) if end < 0 else end + 2
                continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    return
                depth -= 1
            elif depth == 0 and c in ",\n":
                return
            self.i += 1

    def _expr(self):
        c = self._peek()
        if c == "{":
            return self._object()
        m = _IDENT.match(self.s, self.i)
        if m and m.group(0) == "merge":
            self.i = m.end()
            if self._peek() == "(":
                self.i += 1
                return self._merge()
        elif m and m.group(0) == "local" and self.s.startswith(".", m.end()):
            name = _IDENT.match(self.s, m.end() + 1)
            if name:
                self.i = name.end()
                if self._peek() in (",", ")", "}", ""):
                    return _literal_map(self.locals.get(name.group(0)))
        self._skip_expr()
        return None

    def _merge(self):
        values, complete = {}, True
        while True:
            c = self._peek()
            if c == ")":
                self.i += 1
                return values, complete
            if c == "":
                return None
            arg = self._expr()
            if arg is None:
                # An unknown map can add any key and override every key before it.
                values = {k: UNKNOWN for k in values}
                complete = False
            else:
                values.update(arg[0])
                complete = complete and arg[1]
            c = self._peek()
            if c == ",":
                self.i += 1
            elif c != ")":
                return None

    def _object(self):
        self.i += 1
        values, complete = {}, True
        while True:
            c = self._peek()
            if c == "}":
                self.i += 1
                return values, complete
            if c == "":
                return None
            if c == ",":
                self.i += 1
                continue
            key = None
            if c == '"':
                text, template = self._string()
                key = None if template else text
            else:
                m = _IDENT.match(self.s, self.i)
                if not m:
                    return None
                key, self.i = m.group(0), m.end()
            if self._peek() not in ("=", ":"):
                return None
            self.i += 1
            value = UNKNOWN
            if self._peek() == '"':
                text, template = self._string()
                if self._peek() in _VALUE_END:
                    value = text if not template else UNKNOWN
                else:
                    self._skip_expr()
            else:
                self._skip_expr()
            if key is None:
                complete = False  # a computed key could be any annotation
            else:
                values[key] = value


def annotation_map(value, local_maps):
    """Resolve an Ingress ``annotations`` value to ``(values, complete)``.

    Takes an hcl2json map literal as-is. For an expression string such as
    ``${merge(local.x, {...})}``, resolves ``local.<name>`` against
    ``local_maps`` and reads inline ``"key" = "value"`` pairs. Unreadable
    values are UNKNOWN; an unreadable map yields ``({}, False)``.
    """
    if value is None:
        return {}, True
    literal = _literal_map(value)
    if literal is not None:
        return literal
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("${") and text.endswith("}"):
            result = _MapExpr(text[2:-1], local_maps).evaluate()
            if result is not None:
                return result
    return {}, False


def _first_block(cfg, key):
    blocks = block(cfg, key)
    return blocks[0] if blocks else {}


def _annotation_state(ann, complete, key, default):
    """An annotation's value, UNKNOWN, or ``default`` when it is surely absent."""
    if key in ann:
        return ann[key]
    return default if complete else UNKNOWN


def _member(rtype, name, cfg, local_maps):
    """Describe one Ingress, or None if the Load Balancer Controller doesn't own it."""
    ann, complete = annotation_map(_first_block(cfg, "metadata").get("annotations"), local_maps)
    cls = _first_block(cfg, "spec").get("ingress_class_name")
    if not (
        cls == "alb"
        or ann.get("kubernetes.io/ingress.class") == "alb"
        or any(k.startswith(LBC_PREFIX) for k in ann)
    ):
        return None

    scheme = _annotation_state(ann, complete, LBC_PREFIX + "scheme", "internal")
    waf_values = [ann.get(LBC_PREFIX + k) for k in ("wafv2-acl-arn", "waf-acl-id")]
    if any(isinstance(v, str) and v.strip() for v in waf_values):
        waf = True
    elif UNKNOWN in waf_values or not complete:
        waf = None
    else:
        waf = False
    attrs = _annotation_state(ann, complete, LBC_PREFIX + "load-balancer-attributes", "")
    logs = UNKNOWN
    if attrs is not UNKNOWN:
        items = {a.replace(" ", "").lower() for a in attrs.split(",")}
        logs = "access_logs.s3.enabled=true" in items
    return {
        "label": "{}.{}".format(rtype, name),
        "group": _annotation_state(ann, complete, LBC_PREFIX + "group.name", None),
        "scheme": scheme if scheme is UNKNOWN else str(scheme).strip().lower(),
        "waf": waf,
        "logs": None if logs is UNKNOWN else logs,
    }


def _any(values):
    """True if any is True, None if any is unknown, else False."""
    if True in values:
        return True
    return None if None in values else False


def lbc_albs(native_files_node):
    """Group the Ingresses the AWS Load Balancer Controller manages into ALBs.

    An Ingress counts if ``spec.ingress_class_name`` or the
    ``kubernetes.io/ingress.class`` annotation is ``alb``, or it carries any
    ``alb.ingress.kubernetes.io/`` annotation. Ingresses sharing a
    ``group.name`` share one ALB; one without a group is its own ALB.

    Returns a list of ``{label, scheme, waf, access_logs}``, sorted by label.
    ``scheme`` is "internet-facing", "internal" (the controller default) or
    None; ``waf`` and ``access_logs`` are True, False or None. None means the
    Terraform doesn't say statically, and a check must not fail on it.
    """
    if not native_files_node.exists():
        return []
    files = []
    local_maps = {}  # locals are module-scoped: one map per directory
    for f in native_files_node:
        raw = f.get_value_or_default(".hcl")
        if not isinstance(raw, dict):
            continue
        d = posixpath.dirname(str(f.get_value_or_default(".path", "")))
        files.append((d, raw))
        for lb in as_blocks(raw.get("locals")):
            local_maps.setdefault(d, {}).update(lb)

    groups = {}
    for d, raw in files:
        resources = raw.get("resource")
        if not isinstance(resources, dict):
            continue
        for rtype in INGRESS_TYPES:
            named = resources.get(rtype)
            if not isinstance(named, dict):
                continue
            for name, configs in named.items():
                for cfg in as_blocks(configs):
                    m = _member(rtype, name, cfg, local_maps.get(d, {}))
                    if m is None:
                        continue
                    group = m["group"]
                    if isinstance(group, str) and group.strip():
                        key = ("group", group.strip())
                    else:
                        # No group: its own ALB. An unknown group: it may share an
                        # ALB with Ingresses we can't see, so nothing is certain.
                        key = ("ingress", m["label"])
                        if group is UNKNOWN:
                            m = dict(m, waf=m["waf"] or None, logs=m["logs"] or None)
                    groups.setdefault(key, []).append(m)

    albs = []
    for (kind, ident), members in groups.items():
        labels = sorted(set(m["label"] for m in members))
        schemes = [m["scheme"] for m in members]
        if "internet-facing" in schemes:
            scheme = "internet-facing"
        elif UNKNOWN in schemes:
            scheme = None
        else:
            scheme = "internal"
        albs.append({
            "label": 'ALB group "{}" ({})'.format(ident, ", ".join(labels))
            if kind == "group" else "ALB for {}".format(ident),
            "scheme": scheme,
            "waf": _any([m["waf"] for m in members]),
            "access_logs": _any([m["logs"] for m in members]),
        })
    return sorted(albs, key=lambda a: a["label"])
