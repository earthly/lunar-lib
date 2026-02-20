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
