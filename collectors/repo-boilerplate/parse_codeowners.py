#!/usr/bin/env python3
"""Parse a CODEOWNERS file and output structured JSON.

Handles GitHub/GitLab/Bitbucket CODEOWNERS format:
- Lines starting with # are comments
- Empty lines are ignored
- Each rule: <pattern> <owner1> [<owner2> ...]
- Owners: @user, @org/team, or email
- Inline comments (# after owners) are supported
"""

import json
import re
import sys

# Owner format patterns
TEAM_RE = re.compile(r"^@[\w][\w.-]*/[\w][\w.-]*$")  # @org/team-name
USER_RE = re.compile(r"^@[\w][\w.-]*$")  # @username
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")  # user@example.com


def classify_owner(owner):
    """Classify an owner string as 'team', 'user', 'email', or None (invalid)."""
    if TEAM_RE.match(owner):
        return "team"
    if USER_RE.match(owner):
        return "user"
    if EMAIL_RE.match(owner):
        return "email"
    return None


def parse_codeowners(filepath):
    """Parse a CODEOWNERS file and return structured data."""
    rules = []
    errors = []
    all_owners = set()
    team_owners = set()
    individual_owners = set()

    with open(filepath, "r") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n\r")
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            # Split line into tokens (whitespace-separated)
            parts = stripped.split()

            pattern = parts[0]
            raw_owners = parts[1:]

            # Collect owners, stopping at inline comments
            valid_owners = []
            for token in raw_owners:
                if token.startswith("#"):
                    break  # Rest of line is a comment

                kind = classify_owner(token)
                if kind is None:
                    errors.append(
                        {
                            "line": line_num,
                            "message": f"Invalid owner format: '{token}'",
                            "content": stripped,
                        }
                    )
                    continue

                valid_owners.append(token)
                all_owners.add(token)
                if kind == "team":
                    team_owners.add(token)
                else:
                    individual_owners.add(token)

            rules.append(
                {
                    "pattern": pattern,
                    "owners": valid_owners,
                    "owner_count": len(valid_owners),
                    "line": line_num,
                }
            )

    return {
        "exists": True,
        "valid": len(errors) == 0,
        "errors": errors,
        "owners": sorted(all_owners),
        "team_owners": sorted(team_owners),
        "individual_owners": sorted(individual_owners),
        "rules": rules,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <codeowners-file>", file=sys.stderr)
        sys.exit(1)

    result = parse_codeowners(sys.argv[1])
    json.dump(result, sys.stdout, separators=(",", ":"))
