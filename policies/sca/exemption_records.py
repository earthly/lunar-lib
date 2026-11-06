"""Exemption records read at run time from `.compliance.vulnerability_exemptions`.

The `vulnerability-exemptions` collector copies them from a register kept in
one compliance repository. A record covers a finding while all of these hold:
the finding's `cve` matches (ignoring case), the record names the component
being checked, today (UTC) is not past `until`, and the finding has no fix.
Once a fix ships the record stops applying, so `max-severity` takes over.
"""

import datetime
import os

RECORDS_PATH = ".compliance.vulnerability_exemptions.records"


class ExemptionRecord:
    """One register entry that applies to this component today."""

    def __init__(self, cve, until):
        self.cve = cve
        self.until = until

    def _key(self):
        return (self.cve.upper(), self.until)

    def __eq__(self, other):
        return isinstance(other, ExemptionRecord) and self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def __str__(self):
        return f"{self.cve} (until {self.until.isoformat()})"


def load_records(check, component=None, today=None):
    """Return the records that cover this component today, each once.

    Malformed, expired and other components' records are dropped. Without a
    component id nothing applies, so a missing id can't widen what's exempt.
    """
    if component is None:
        component = os.environ.get("LUNAR_COMPONENT_ID", "")
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    node = check.get_node(RECORDS_PATH)
    if not component or not node.exists():
        return []
    raw = node.get_value()
    records = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict) or entry.get("component") != component:
            continue
        cve = entry.get("cve")
        until = entry.get("until")
        if not isinstance(cve, str) or not cve.strip() or not isinstance(until, str):
            continue
        try:
            until = datetime.date.fromisoformat(until.strip())
        except ValueError:
            continue
        record = ExemptionRecord(cve.strip(), until)
        if today <= until and record not in records:
            records.append(record)
    return records


def find_record(records, cve, fixable):
    """Return the record covering a finding, or None. A fixable finding never is."""
    if fixable or not cve:
        return None
    for record in records:
        if record.cve.upper() == cve.upper():
            return record
    return None
