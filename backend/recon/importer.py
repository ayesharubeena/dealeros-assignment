"""CSV -> database. Contract: every data row in = one row stored. Nothing dropped."""
import csv
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from .compare import ARecord, BEntry, compare
from .models import Disagreement, Location, SystemARecord, SystemBEntry
from .parsing import normalise_location, normalise_ref, parse_amount, parse_date


@dataclass
class ImportSummary:
    locations: int
    a_rows_read: int
    a_rows_stored: int
    b_rows_read: int
    b_rows_stored: int
    findings: int
    findings_by_reason: dict
    quarantined: int   # findings no tenant can see (owner org unknown)


def _read(path):
    # utf-8-sig survives a BOM; strip header names in case of stray spaces
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
        return list(reader)


def _g(row, key):
    return (row.get(key) or "")


@transaction.atomic
def run_import(data_dir):
    data_dir = Path(data_dir)
    loc_rows = _read(data_dir / "locations.csv")
    a_rows = _read(data_dir / "system_a.csv")
    b_rows = _read(data_dir / "system_b.csv")

    # Re-running replaces everything, so the import is idempotent.
    for model in (Disagreement, SystemBEntry, SystemARecord, Location):
        model.objects.all().delete()

    Location.objects.bulk_create(
        Location(location_id=normalise_location(r["location_id"]) or r["location_id"],
                 org_id=r["org_id"].strip(), name=r["location_name"].strip())
        for r in loc_rows)

    a_objs = [SystemARecord(
        row_number=i, record_id=_g(r, "record_id").strip(),
        location_id=normalise_location(_g(r, "location_id")) or "",
        event_date=parse_date(_g(r, "event_date")),
        category_code=_g(r, "category_code").strip(), actor_id=_g(r, "actor_id").strip(),
        base_value=parse_amount(_g(r, "base_value")), adjustment=parse_amount(_g(r, "adjustment")),
        total_value=parse_amount(_g(r, "total_value")), raw_total_value=_g(r, "total_value"),
        state=_g(r, "state").strip()) for i, r in enumerate(a_rows, start=2)]
    SystemARecord.objects.bulk_create(a_objs)

    b_objs = [SystemBEntry(
        row_number=i, entry_id=_g(r, "entry_id").strip(), raw_ref=_g(r, "record_ref"),
        record_ref=normalise_ref(_g(r, "record_ref")) or "",
        location_id=normalise_location(_g(r, "location_id")) or "",
        recorded_on=parse_date(_g(r, "recorded_on")),
        value=parse_amount(_g(r, "value")), raw_value=_g(r, "value"),
        label=_g(r, "label").strip()) for i, r in enumerate(b_rows, start=2)]
    SystemBEntry.objects.bulk_create(b_objs)

    stored_a, stored_b = SystemARecord.objects.count(), SystemBEntry.objects.count()
    if (stored_a, stored_b) != (len(a_rows), len(b_rows)):
        raise RuntimeError(f"Row count mismatch: A {len(a_rows)}->{stored_a}, B {len(b_rows)}->{stored_b}")

    org_of = dict(Location.objects.values_list("location_id", "org_id"))
    findings = compare(
        [ARecord(o.row_number, o.record_id, o.location_id or None, o.event_date,
                 o.total_value, o.base_value) for o in SystemARecord.objects.order_by("row_number")],
        [BEntry(o.row_number, o.entry_id, o.record_ref or None, o.raw_ref, o.location_id or None,
                o.recorded_on, o.value, o.raw_value) for o in SystemBEntry.objects.order_by("row_number")],
        org_of)
    Disagreement.objects.bulk_create(Disagreement(
        reason=f.reason, record_id=f.record_id or "", entry_ids=f.entry_ids,
        a_value=f.a_value, b_value=f.b_value, a_location=f.a_location, b_location=f.b_location,
        a_org=f.a_org, b_org=f.b_org, sort_value=f.sort_value, detail=f.detail) for f in findings)

    by_reason = {}
    for f in findings:
        by_reason[f.reason] = by_reason.get(f.reason, 0) + 1
    return ImportSummary(len(loc_rows), len(a_rows), stored_a, len(b_rows), stored_b,
                         len(findings), by_reason,
                         sum(1 for f in findings if f.a_org is None and f.b_org is None))
