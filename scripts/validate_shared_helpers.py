#!/usr/bin/env python3
"""Fail when the copies of a shared bash helper drift apart.

Plugins can't source each other's files, so a helper that several plugins need
is copied into each of them. Every copy listed in SHARED must match the others
line for line once these are normalized away:

  * indentation and blank lines (plugins indent by 2 or 4 spaces);
  * what each plugin owns: its STS role session name (`lunar-<plugin>-collector`
    or `-cataloger`) and its noun in one log line ("the collector's ...").

A fix to one copy belongs in all of them; this check is what makes that stick.

collectors/ci-archive/aws-credentials.sh is a deliberately diverged variant of
the same AWS helpers (S3 region, external ID, endpoint override), so it isn't in
the group.

Usage:
    python scripts/validate_shared_helpers.py
    python scripts/validate_shared_helpers.py --self-test
"""

import difflib
import os
import re
import sys

# Each group: the functions that are copied, and every file holding a copy.
SHARED = [
    {
        "name": "Backstage AWS SigV4 helpers",
        "functions": [
            "parse_sts_credentials",
            "resolve_aws_credentials",
            "assume_role_chain",
            "url_escape",
        ],
        "files": [
            "collectors/backstage/main.sh",
            "catalogers/backstage/main.sh",
            "collectors/pagerduty/backstage.sh",
        ],
    },
]

# What a copy may say differently, mapped to a placeholder before comparing.
ALLOWED = [
    (re.compile(r"\blunar-[a-z0-9-]+-(?:collector|cataloger)\b"), "<session-name>"),
    (re.compile(r"\b(?:collector|cataloger)'s\b"), "<plugin>'s"),
]


def extract(source, name):
    """Return the normalized lines of every definition of `name` in `source`.

    A definition starts at `name() {` and ends at the first `}` line indented
    like its opening line, or on the same line for a one-liner.
    """
    opening = re.compile(r"^(\s*)(?:function\s+)?" + re.escape(name) + r"\s*\(\)\s*\{(.*)$")
    lines = source.split("\n")
    found = []
    i = 0
    while i < len(lines):
        m = opening.match(lines[i])
        if not m:
            i += 1
            continue
        indent, rest = m.group(1), m.group(2)
        body = [lines[i]]
        if not re.search(r"\}\s*$", rest):
            j = i + 1
            while j < len(lines):
                body.append(lines[j])
                if lines[j].strip() == "}" and lines[j][: len(indent)] == indent and not lines[j][len(indent)].isspace():
                    break
                j += 1
            else:
                body = None
            i = j
        if body is not None:
            found.append(normalize(body))
        i += 1
    return found


def normalize(lines):
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for pattern, placeholder in ALLOWED:
            line = pattern.sub(placeholder, line)
        out.append(line)
    return out


def check(read, groups=SHARED):
    """Return a list of error strings. `read(path)` returns a file's text."""
    errors = []
    for group in groups:
        copies = {}
        for path in group["files"]:
            try:
                source = read(path)
            except OSError as e:
                errors.append(f"{group['name']}: cannot read {path}: {e.strerror}")
                continue
            for fn in group["functions"]:
                defs = extract(source, fn)
                if len(defs) != 1:
                    what = "is missing" if not defs else f"is defined {len(defs)} times"
                    errors.append(f"{group['name']}: {fn}() {what} in {path}")
                    continue
                copies.setdefault(fn, []).append((path, defs[0]))
        for fn, versions in copies.items():
            base_path, base = versions[0]
            for path, body in versions[1:]:
                if body != base:
                    diff = "\n".join(
                        "    " + d
                        for d in difflib.unified_diff(base, body, base_path, path, lineterm="", n=1)
                    )
                    errors.append(f"{group['name']}: {fn}() in {path} differs from {base_path}:\n{diff}")
    return errors


def read_file(path):
    with open(path) as f:
        return f.read()


# --- self-test -------------------------------------------------------------

COPY_A = """
helper() {
  local x="$1"
  curl --data-urlencode "RoleSessionName=lunar-backstage-collector" "$x"
  echo "Attach a role to the collector's service account" >&2

  if [ -n "$x" ]; then
    echo ok
  fi
}
quote() { jq -rn --arg s "$1" '$s|@uri'; }
"""

# Same helpers, 4-space indent, a blank line less, its own session name and noun.
COPY_B = """
    helper() {
        local x="$1"
        curl --data-urlencode "RoleSessionName=lunar-pagerduty-collector" "$x"
        echo "Attach a role to the cataloger's service account" >&2
        if [ -n "$x" ]; then
            echo ok
        fi
    }
    quote() { jq -rn --arg s "$1" '$s|@uri'; }
"""

GROUP = [{"name": "test", "functions": ["helper", "quote"], "files": ["a.sh", "b.sh"]}]


def self_test():
    def run(a, b):
        files = {"a.sh": a, "b.sh": b}
        return "\n".join(check(lambda p: files[p], GROUP))

    cases = [
        ("a changed line", COPY_B.replace("echo ok", "echo okay"), ["helper()", "b.sh", "+echo okay"]),
        ("a changed one-liner", COPY_B.replace("@uri", "@sh"), ["quote()", "@sh"]),
        ("a missing function", COPY_B.replace("quote()", "escape()"), ["quote() is missing in b.sh"]),
        ("a duplicate definition", COPY_B + COPY_B, ["defined 2 times"]),
        ("a different session-name shape", COPY_B.replace("lunar-pagerduty-collector", "pagerduty"), ["helper()"]),
    ]
    failures = []
    if run(COPY_A, COPY_B):
        failures.append("  allowed differences were reported:\n" + run(COPY_A, COPY_B))
    else:
        print("  OK  accepts: indentation, blank lines, session name, plugin noun")
    for label, b, expected in cases:
        out = run(COPY_A, b)
        missing = [token for token in expected if token not in out]
        if not out or missing:
            failures.append(f"  {label}: expected a failure mentioning {missing or expected}, got:\n{out}")
        else:
            print(f"  OK  rejects: {label}")
    if failures:
        print("\nSelf-test FAILED:")
        print("\n".join(failures))
        return 1
    print(f"Self-test passed (1 accepted, {len(cases)} rejected).")
    return 0


def main():
    if "--self-test" in sys.argv[1:]:
        return self_test()
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    errors = check(read_file)
    if errors:
        print("Shared helper copies have drifted:\n")
        for e in errors:
            print(f"  {e}\n")
        print("Apply the same change to every copy listed in scripts/validate_shared_helpers.py.")
        return 1
    total = sum(len(g["files"]) for g in SHARED)
    print(f"OK: {len(SHARED)} shared helper group(s), {total} copies in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
