"""Where disagreements are decided.

`compare()` is a pure function: plain objects in, plain objects out, no
database. That is deliberate -- it is the part that must be right, so it is
the part that is easiest to test.

Reasons produced (see REASONS):
  missing_in_b      A record has no entry in B
  orphan_entry      B entry points at a record that does not exist in A
  duplicate_entry   one A record has several B entries that are NOT a legit split
  value_mismatch    both sides readable, amounts differ
  value_unreadable  a side's amount is blank / not a number
  location_mismatch the two systems put the record at different locations
  date_mismatch     event_date (A) differs from recorded_on (B)
  duplicate_record_in_a  the same record_id appears twice in A
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

REASONS = [
    ("missing_in_b", "Missing in System B"),
    ("orphan_entry", "B entry points at no A record"),
    ("duplicate_entry", "Duplicate B entry"),
    ("value_mismatch", "Value differs"),
    ("value_unreadable", "Value blank / unreadable"),
    ("location_mismatch", "Location differs"),
    ("date_mismatch", "Date differs"),
    ("duplicate_record_in_a", "Duplicate record in System A"),
]

CENT = Decimal("0.01")


@dataclass(frozen=True)
class ARecord:
    row: int
    record_id: str
    location_id: Optional[str]
    event_date: Optional[date]
    total_value: Optional[Decimal]
    base_value: Optional[Decimal] = None   # only used to explain mismatches


@dataclass(frozen=True)
class BEntry:
    row: int
    entry_id: str
    record_ref: Optional[str]              # already normalised, None if unreadable
    raw_ref: str
    location_id: Optional[str]
    recorded_on: Optional[date]
    value: Optional[Decimal]
    raw_value: str = ""


@dataclass
class Finding:
    reason: str
    record_id: Optional[str]
    entry_ids: list = field(default_factory=list)
    a_value: str = ""          # display text, "" = side absent
    b_value: str = ""
    a_location: str = ""
    b_location: str = ""
    a_org: Optional[str] = None
    b_org: Optional[str] = None
    sort_value: Optional[Decimal] = None
    detail: str = ""


def _fmt(d):
    return f"{d:.2f}" if d is not None else ""


def _q(d):
    return d.quantize(CENT) if d is not None else None


def compare(a_records, b_entries, org_of):
    """org_of: {location_id: org_id}. Unknown locations map to org None."""
    org = lambda loc: org_of.get(loc) if loc else None  # noqa: E731
    findings = []

    # ---- index A, catching duplicate record_ids rather than overwriting ----
    a_by_id = defaultdict(list)
    for rec in a_records:
        a_by_id[rec.record_id].append(rec)
    a_index = {}
    for rid, recs in a_by_id.items():
        a_index[rid] = recs[0]
        if len(recs) > 1:
            first = recs[0]
            findings.append(Finding(
                "duplicate_record_in_a", rid,
                a_value=_fmt(first.total_value), a_location=first.location_id or "",
                a_org=org(first.location_id), sort_value=first.total_value,
                detail=f"{len(recs)} rows in System A share this record_id "
                       f"(rows {', '.join(str(r.row) for r in recs)}); first row used for comparison",
            ))

    # ---- group B entries by the A record they point at ----
    entries_for = defaultdict(list)
    for e in b_entries:
        if e.record_ref is None or e.record_ref not in a_index:
            detail = (f'reference "{e.raw_ref}" cannot be read as a record id'
                      if e.record_ref is None
                      else f"{e.record_ref} does not exist in System A")
            findings.append(Finding(
                "orphan_entry", e.record_ref, [e.entry_id],
                b_value=e.raw_value.strip() if e.value is None else _fmt(e.value),
                b_location=e.location_id or "", b_org=org(e.location_id),
                sort_value=e.value, detail=detail,
            ))
        else:
            entries_for[e.record_ref].append(e)

    # ---- per A record ----
    for rid, a in a_index.items():
        entries = entries_for.get(rid, [])
        a_org = org(a.location_id)

        if not entries:
            findings.append(Finding(
                "missing_in_b", rid, a_value=_fmt(a.total_value),
                a_location=a.location_id or "", a_org=a_org,
                sort_value=a.total_value, detail="No System B entry references this record",
            ))
            continue

        is_split = False
        if len(entries) > 1:
            parts = [e.value for e in entries]
            is_split = (a.total_value is not None
                        and all(p is not None for p in parts)
                        and _q(sum(parts)) == _q(a.total_value))
            if not is_split:
                findings.append(Finding(
                    "duplicate_entry", rid, [e.entry_id for e in entries],
                    a_value=_fmt(a.total_value),
                    b_value=" / ".join(e.raw_value.strip() or "(blank)" for e in entries),
                    a_location=a.location_id or "", b_location=entries[0].location_id or "",
                    a_org=a_org, b_org=org(entries[0].location_id),
                    sort_value=a.total_value,
                    detail=f"{len(entries)} System B entries for one record: "
                           f"{', '.join(e.entry_id for e in entries)}",
                ))

        def make(reason, e, detail, a_val=None, b_val=None):
            return Finding(
                reason, rid, [x.entry_id for x in entries] if is_split else [e.entry_id],
                a_value=a_val if a_val is not None else _fmt(a.total_value),
                b_value=b_val if b_val is not None else (e.raw_value.strip() or "(blank)"),
                a_location=a.location_id or "", b_location=e.location_id or "",
                a_org=a_org, b_org=org(e.location_id),
                sort_value=a.total_value, detail=detail,
            )

        # value check: on the SUM for a legit split (already proven equal => nothing
        # to report), otherwise entry by entry.
        if not is_split:
            for e in entries:
                if a.total_value is None or e.value is None:
                    side = "System A" if a.total_value is None else "System B"
                    findings.append(make(
                        "value_unreadable", e,
                        f"{side} amount is blank or not a number "
                        f"(A={_fmt(a.total_value) or 'unreadable'}, B={e.raw_value.strip()!r})"))
                elif _q(a.total_value) != _q(e.value):
                    why = ""
                    if a.base_value is not None and _q(e.value) == _q(a.base_value):
                        why = " -- B equals A's base_value, so the adjustment looks dropped"
                    findings.append(make(
                        "value_mismatch", e,
                        f"difference {_q(e.value - a.total_value)}{why}"))

        # location / date are checked on every entry, split or not
        for e in entries:
            if a.location_id != e.location_id:
                cross = " (different orgs)" if org(a.location_id) != org(e.location_id) else ""
                findings.append(make(
                    "location_mismatch", e,
                    f"A says {a.location_id}, B says {e.location_id}{cross}"))
            if a.event_date != e.recorded_on:
                findings.append(make(
                    "date_mismatch", e,
                    f"A event_date {a.event_date} vs B recorded_on {e.recorded_on}"))

    return findings
