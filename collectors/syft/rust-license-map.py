"""Extract license metadata from cargo registry cache into a JSON map.

Reads Cargo.toml files from the cargo registry source directory and outputs
a JSON object mapping "crate_name@version" to SPDX license expressions.
"""
import os
import json
import re
import glob
import sys

registry_src = sys.argv[1]
output_path = sys.argv[2]

license_map = {}
for toml_path in glob.glob(os.path.join(registry_src, "*", "*", "Cargo.toml")):
    crate_dir = os.path.basename(os.path.dirname(toml_path))
    m = re.match(r"^(.+)-(\d+\..*)$", crate_dir)
    if not m:
        continue
    crate_name, crate_version = m.group(1), m.group(2)
    with open(toml_path) as f:
        for line in f:
            lm = re.match(r'^license\s*=\s*["\']([^"\']+)["\']', line)
            if lm:
                lic = lm.group(1).strip().replace("/", " OR ")
                license_map[crate_name + "@" + crate_version] = lic
                break

json.dump(license_map, open(output_path, "w"))
print(f"Built license map for {len(license_map)} Rust crates", file=sys.stderr)
