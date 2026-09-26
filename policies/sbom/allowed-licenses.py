"""Fail when an SBOM component carries a license the allow-list doesn't admit."""

import re
import sys
sys.path.insert(0, ".")
from helpers import parse_patterns
from lunar_policy import Check, variable_or_default
from spdx_exceptions import SPDX_EXCEPTIONS

MAX_NAMED = 5

# SPDX 2.3 §7.13 / §7.15: these mean the field carries no license at all.
SPDX_NO_LICENSE = {"NOASSERTION", "NONE"}

OPERATORS = {"AND", "OR", "WITH"}


def squash(text):
    return " ".join(text.split())


class Matcher:
    """Matches one license identifier against the allow-list, case-insensitively.

    An entry admits an identifier it equals, or that it matches in full as a regex.
    """

    def __init__(self, entries):
        try:
            self._patterns = [re.compile(e, re.IGNORECASE) for e in entries]
        except re.error as e:
            raise ValueError(f"Invalid regex in allowed_licenses: {e}")
        self._literals = {squash(e).casefold() for e in entries}

    def literal(self, text):
        return squash(text).casefold() in self._literals

    def __call__(self, identifier):
        return self.literal(identifier) or any(p.fullmatch(identifier) for p in self._patterns)


def parse_expression(text):
    """Parse an SPDX license expression (SPDX 2.3 Annex D).

    Returns ("or" | "and", [children]) or ("license", identifier, exception_or_None).
    Precedence is WITH, then AND, then OR, and operators are case-sensitive (Annex
    D.2), so "MIT with modifications" stays free text. Raises ValueError if `text`
    isn't an expression.
    """
    tokens = re.findall(r"[()]|[^\s()]+", text)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take():
        nonlocal pos
        pos += 1
        return tokens[pos - 1] if pos <= len(tokens) else None

    def is_op(token, op):
        return token == op

    def is_identifier(token):
        return token is not None and token not in ("(", ")") and token not in OPERATORS

    def parse_or():
        children = [parse_and()]
        while is_op(peek(), "OR"):
            take()
            children.append(parse_and())
        return children[0] if len(children) == 1 else ("or", children)

    def parse_and():
        children = [parse_simple()]
        while is_op(peek(), "AND"):
            take()
            children.append(parse_simple())
        return children[0] if len(children) == 1 else ("and", children)

    def parse_simple():
        token = take()
        if token == "(":
            inner = parse_or()
            if take() != ")":
                raise ValueError(f"unbalanced parentheses in {text!r}")
            return inner
        if not is_identifier(token):
            raise ValueError(f"expected a license identifier in {text!r}")
        if not is_op(peek(), "WITH"):
            return ("license", token, None)
        take()
        exception = take()
        if not is_identifier(exception):
            raise ValueError(f"expected an exception after WITH in {text!r}")
        return ("license", token, exception)

    tree = parse_or()
    if peek() is not None:
        raise ValueError(f"unexpected {peek()!r} in {text!r}")
    return tree


def license_allowed(text, matcher, refs=None):
    """Whether a license string from the SBOM is admitted.

    `refs` maps an SPDX document's LicenseRef IDs (casefolded) to their extracted
    names, so a LicenseRef is admitted by whatever admits the license it names.
    """
    if matcher.literal(text):
        return True
    try:
        tree = parse_expression(text)
    except (ValueError, RecursionError):
        # Free text such as "MIT License": only an exact entry admits it, so a
        # pattern like "MIT.*" can't stretch across a second license.
        return False
    return _tree_allowed(tree, matcher, refs or {})


def _tree_allowed(tree, matcher, refs):
    kind = tree[0]
    if kind == "or":
        return any(_tree_allowed(child, matcher, refs) for child in tree[1])
    if kind == "and":
        return all(_tree_allowed(child, matcher, refs) for child in tree[1])
    _, identifier, exception = tree
    if exception:
        if matcher(f"{identifier} WITH {exception}"):
            return True
        # A listed SPDX exception only relaxes the license, so the bare license
        # admitting it is enough. Anything else after WITH, such as the Commons
        # Clause (a restriction), is admitted only by listing the full pair.
        if exception.casefold() not in SPDX_EXCEPTIONS:
            return False
    if matcher(identifier):
        return True
    # "X+" is "X or any later version", so admitting X admits it.
    if identifier.endswith("+") and matcher(identifier[:-1]):
        return True
    name = refs.get(identifier.casefold())
    return name is not None and license_allowed(name, matcher)


def license_strings(component):
    """The license strings a CycloneDX component or SPDX package carries, as written."""
    found = []
    licenses = component.get("licenses")
    for entry in licenses if isinstance(licenses, list) else []:
        if not isinstance(entry, dict):
            continue
        lic = entry.get("license")
        if isinstance(lic, dict):
            for key in ("id", "name"):
                value = lic.get(key)
                if isinstance(value, str) and value.strip():
                    found.append(value)
                    break
        expression = entry.get("expression")
        if isinstance(expression, str) and expression.strip():
            found.append(expression)
    # SPDX: the concluded license governs; fall back to the declared one.
    for key in ("licenseConcluded", "licenseDeclared"):
        value = component.get(key)
        if isinstance(value, str) and value.strip() and value.strip().upper() not in SPDX_NO_LICENSE:
            found.append(value)
            break
    return found


def sbom_documents(c):
    """(components, LicenseRef names) for each SBOM document, and whether any SBOM exists."""
    documents = []
    has_sbom = False
    for prefix in (".sbom.auto", ".sbom.cicd"):
        node = c.get_node(prefix)
        if not node.exists():
            continue
        has_sbom = True
        cyclonedx = node.get_node(".cyclonedx.components")
        if cyclonedx.exists():
            documents.append((cyclonedx.get_value(), {}))
        spdx = node.get_node(".spdx.packages")
        if spdx.exists():
            refs = {}
            for info in node.get_value_or_default(".spdx.hasExtractedLicensingInfos", []) or []:
                if not isinstance(info, dict):
                    continue
                ref, name = info.get("licenseId"), info.get("name")
                if isinstance(ref, str) and isinstance(name, str) and name.strip() \
                        and name.strip().upper() not in SPDX_NO_LICENSE:
                    refs[ref.casefold()] = name
            documents.append((spdx.get_value(), refs))
    return documents, has_sbom


def label(component):
    name = component.get("name") or "<unknown>"
    version = component.get("version") or component.get("versionInfo")
    return f"{name}@{version}" if version else name


def main(node=None):
    c = Check("allowed-licenses", "Checks SBOM component licenses against an allow-list", node=node)
    with c:
        entries = parse_patterns(variable_or_default("allowed_licenses", ""))
        if not entries:
            c.skip("No allowed licenses configured. Set `allowed_licenses` to enforce this check.")
        matcher = Matcher(entries)

        documents, has_sbom = sbom_documents(c)
        if not has_sbom:
            c.skip("No SBOM data available")

        offenders = {}
        total = licensed = 0
        for components, refs in documents:
            verdicts = {}
            for component in components if isinstance(components, list) else []:
                if not isinstance(component, dict):
                    continue
                total += 1
                texts = license_strings(component)
                if texts:
                    licensed += 1
                for text in texts:
                    if text not in verdicts:
                        verdicts[text] = license_allowed(text, matcher, refs)
                    if verdicts[text]:
                        continue
                    shown = squash(text)
                    if shown.casefold() in refs:
                        shown += f" ({squash(refs[shown.casefold()])})"
                    offenders.setdefault(shown, set()).add(label(component))

        if not total:
            c.skip("SBOM has no components")
        # A component with no license data is has-licenses' concern, not a second failure here.
        if not licensed:
            c.skip("No SBOM component carries license data")

        for shown in sorted(offenders, key=str.casefold):
            names = sorted(offenders[shown])
            listed = ", ".join(names[:MAX_NAMED])
            if len(names) > MAX_NAMED:
                listed += f", +{len(names) - MAX_NAMED} more"
            c.fail(f"License '{shown}' is not in allowed_licenses: {listed}")
    return c


if __name__ == "__main__":
    main()
