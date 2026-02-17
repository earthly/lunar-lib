"""Parse dependencies from pyproject.toml.

Outputs one dependency per line in the format: name==version (or just name if no version).
"""
import re
import sys

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        sys.exit(0)

with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)

# Check [project.dependencies] (PEP 621)
project_deps = data.get("project", {}).get("dependencies", [])
for dep in project_deps:
    m = re.match(r"^([A-Za-z0-9_.-]+)\s*(?:[><=!~]+\s*(.+?))?(?:;.*)?$", dep.strip())
    if m:
        name = m.group(1)
        version = m.group(2) or ""
        version = version.split(",")[0].strip() if version else ""
        print(f"{name}=={version}" if version else name)

# Check [tool.poetry.dependencies] (Poetry)
poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
if poetry_deps and not project_deps:
    for name, spec in poetry_deps.items():
        if name.lower() == "python":
            continue
        version = ""
        if isinstance(spec, str):
            version = spec.lstrip("^~>=<!")
        elif isinstance(spec, dict):
            version = spec.get("version", "").lstrip("^~>=<!")
        print(f"{name}=={version}" if version else name)
