from lunar_policy import Check, variable_or_default

MAX_LISTED = 10

# Classic bypass allowances name users, teams and apps by login/slug; match them
# with the actor types rulesets use for the same kinds of actor.
CLASSIC_ALLOWANCE_TYPES = (("users", "User"), ("teams", "Team"), ("apps", "Integration"))


class AllowListError(ValueError):
    """A malformed allowed_bypass_actors entry.

    Raised rather than skipped, so a typo can never read as "allow everything".
    """


def parse_allowed(raw):
    """Parse allowed_bypass_actors: `<ActorType>` or `<ActorType>:<id>` entries,
    separated by newlines or commas. A `#` comments out the rest of its line;
    comments are stripped before the comma split so a rationale can hold commas.
    """
    allowed = []
    for line in raw.splitlines():
        for entry in line.split("#", 1)[0].split(","):
            entry = entry.strip()
            if not entry:
                continue
            actor_type, sep, ident = (part.strip() for part in entry.partition(":"))
            if not actor_type or (sep and not ident):
                raise AllowListError(
                    f"allowed_bypass_actors: expected '<ActorType>' or '<ActorType>:<id>', got {entry!r}"
                )
            allowed.append((actor_type.lower(), ident or None))
    return allowed


def is_allowed(allowed, actor_type, ident):
    return any(
        t == actor_type.lower() and (i is None or i == str(ident))
        for t, i in allowed
    )


def main(node=None, allowed_override=None):
    c = Check("disallow-bypass-actors", "Nobody should be able to bypass branch protection", node=node)
    with c:
        # Parsed before any data is read: a malformed list must error the check
        # rather than allow anything.
        raw = allowed_override if allowed_override is not None else variable_or_default("allowed_bypass_actors", "")
        allowed = parse_allowed(raw)

        bp = c.get_node(".vcs.branch_protection")
        if not bp.exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        if not bp.get_value(".enabled"):
            c.fail("Branch protection is not enabled")
            return c

        violations = []
        unseen = []

        if bp.get_value_or_default(".source", "") == "classic":
            enforce_admins = bp.get_node(".enforce_admins")
            if not enforce_admins.exists():
                unseen.append("whether classic branch protection applies to administrators")
            elif enforce_admins.get_value() is not True:
                violations.append(
                    "classic branch protection does not apply to administrators "
                    "(\"Do not allow bypassing the above settings\" is off)"
                )
            allowances = bp.get_value_or_default(".bypass_pull_request_allowances", {})
            for kind, actor_type in CLASSIC_ALLOWANCE_TYPES:
                for name in allowances.get(kind, []):
                    if not is_allowed(allowed, actor_type, name):
                        violations.append(
                            f"classic branch protection lets {actor_type} {name} bypass the pull-request requirement"
                        )

        rulesets = bp.get_node(".rulesets")
        if not rulesets.exists():
            unseen.append("the rulesets on the branch (collected for GitHub by the github collector)")
        else:
            for rs in rulesets.get_value():
                label = f"ruleset '{rs.get('name', rs.get('id'))}' ({rs.get('source', 'unknown source')})"
                if "bypass_actors" not in rs:
                    unseen.append(
                        f"the bypass actors of {label} — GitHub shows them only to a token "
                        "with write access to the ruleset"
                    )
                    continue
                for actor in rs["bypass_actors"]:
                    actor_type = actor.get("actor_type", "unknown")
                    actor_id = actor.get("actor_id")
                    if is_allowed(allowed, actor_type, actor_id):
                        continue
                    who = actor_type if actor_id is None else f"{actor_type} {actor_id}"
                    violations.append(f"{label} lets {who} bypass it ({actor.get('bypass_mode', 'always')})")

        branch = bp.get_value_or_default(".branch", "the default branch")
        if violations:
            listed = "".join(f"\n    * {v}" for v in violations[:MAX_LISTED])
            if len(violations) > MAX_LISTED:
                listed += f"\n    * +{len(violations) - MAX_LISTED} more (see .vcs.branch_protection)"
            c.fail(f"Branch protection on {branch} can be bypassed:{listed}")
        elif unseen:
            # A bypass list we could not read is unknown, not empty: never pass on it.
            c.skip(f"Could not see {'; '.join(unseen)}.")
    return c


if __name__ == "__main__":
    main()
