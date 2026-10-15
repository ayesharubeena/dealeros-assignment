"""Importer + API tests against the real CSVs. Includes the tenant-boundary tests."""
import json
from pathlib import Path

from django.test import TestCase

from recon.importer import run_import
from recon.models import Disagreement, SystemARecord, SystemBEntry

DATA = Path(__file__).resolve().parents[3] / "data"
ORG_LOCATIONS = {"ORG-A": {"LOC-101", "LOC-102", "LOC-103"}, "ORG-B": {"LOC-201", "LOC-202"}}


class TestImporter(TestCase):
    def test_no_row_is_dropped_and_import_is_repeatable(self):
        for _ in range(2):   # second run proves it replaces rather than duplicates
            s = run_import(DATA)
            self.assertEqual((s.a_rows_read, s.a_rows_stored), (120, 120))
            self.assertEqual((s.b_rows_read, s.b_rows_stored), (121, 121))
        self.assertEqual(SystemARecord.objects.count(), 120)
        self.assertEqual(SystemBEntry.objects.count(), 121)

    def test_dirty_values_are_kept_raw_and_parsed_where_possible(self):
        run_import(DATA)
        self.assertEqual(SystemBEntry.objects.get(entry_id="ENT/2026/4064").value, 125400)
        self.assertEqual(SystemBEntry.objects.get(entry_id="ENT/2026/4064").raw_value, "1,25,400.00")
        blank = SystemBEntry.objects.get(entry_id="ENT/2026/4050")
        self.assertIsNone(blank.value)
        self.assertEqual(SystemBEntry.objects.get(entry_id="ENT/2026/4034").record_ref, "REC-1034")
        self.assertEqual(SystemBEntry.objects.get(entry_id="ENT/2026/4112").record_ref, "REC-1112")

    def test_expected_findings_on_the_supplied_data(self):
        s = run_import(DATA)
        self.assertEqual(s.findings_by_reason, {
            "missing_in_b": 2, "orphan_entry": 1, "duplicate_entry": 1,
            "value_mismatch": 4, "value_unreadable": 1,
            "location_mismatch": 1, "date_mismatch": 1})
        self.assertEqual(s.quarantined, 0)

    def test_non_errors_are_not_flagged(self):
        run_import(DATA)
        flagged = set(Disagreement.objects.values_list("record_id", flat=True))
        # dirty-but-resolvable refs, the REC-1055 split, and the VOIDED record
        for rid in ["REC-1034", "REC-1112", "REC-1070", "REC-1055", "REC-1019"]:
            self.assertNotIn(rid, flagged)


class TestTenantBoundary(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_import(DATA)

    def get(self, **params):
        return self.client.get("/api/disagreements", params)

    def test_org_is_required_and_must_exist(self):
        self.assertEqual(self.get().status_code, 400)
        self.assertEqual(self.get(org="ORG-ZZZ").status_code, 404)

    def test_each_org_sees_no_location_of_the_other_org_anywhere_in_the_response(self):
        for org, other in [("ORG-A", "ORG-B"), ("ORG-B", "ORG-A")]:
            body = self.get(org=org).content.decode()
            self.assertTrue(json.loads(body)["results"])
            for loc in ORG_LOCATIONS[other]:
                self.assertNotIn(loc, body, f"{org} response leaked {loc}")

    def test_cross_org_mismatch_is_redacted_for_both_sides(self):
        a = [r for r in self.get(org="ORG-A").json()["results"] if r["reason"] == "location_mismatch"][0]
        b = [r for r in self.get(org="ORG-B").json()["results"] if r["reason"] == "location_mismatch"][0]
        self.assertEqual((a["a_location"], a["b_location"], a["redacted"]), ("LOC-102", "", True))
        self.assertEqual((b["a_location"], b["b_location"], b["redacted"]), ("", "LOC-201", True))
        self.assertEqual(a["entry_ids"], [])        # B's entry id is B-owner's data
        self.assertEqual(b["record_id"], "")        # A's record id is A-owner's data

    def test_filter_filters_but_never_widens_the_tenant(self):
        rows = self.get(org="ORG-B", reason="missing_in_b").json()["results"]
        self.assertEqual([r["record_id"] for r in rows], ["REC-1061"])   # 1015 is ORG-A's

    def test_sort_by_value_both_directions(self):
        asc = [float(r["sort_value"]) for r in self.get(org="ORG-A", ordering="value").json()["results"]
               if r["sort_value"]]
        desc = [float(r["sort_value"]) for r in self.get(org="ORG-A", ordering="-value").json()["results"]
                if r["sort_value"]]
        self.assertEqual(asc, sorted(asc))
        self.assertEqual(desc, sorted(desc, reverse=True))
