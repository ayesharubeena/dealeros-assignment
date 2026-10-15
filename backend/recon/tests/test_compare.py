"""Tests for the part that matters: where disagreements are decided.
One test per kind of disagreement, plus the cases that must NOT be flagged.
No database needed -- compare() is a pure function."""
from datetime import date
from decimal import Decimal as D
from unittest import TestCase

from recon.compare import ARecord, BEntry, compare

ORGS = {"LOC-1": "ORG-A", "LOC-2": "ORG-B"}
DAY = date(2026, 3, 1)


def a(rid="REC-1", loc="LOC-1", total="100.00", base="80.00", day=DAY, row=2):
    return ARecord(row, rid, loc, day, D(total) if total is not None else None, D(base))


def b(eid="E1", ref="REC-1", loc="LOC-1", value="100.00", day=DAY, raw=None, row=2):
    return BEntry(row, eid, ref, ref or "", loc, day,
                  D(value) if value is not None else None,
                  raw if raw is not None else (value or ""))


def reasons(findings):
    return sorted(f.reason for f in findings)


class TestEachKindOfDisagreement(TestCase):
    def test_missing_in_b(self):
        found = compare([a()], [], ORGS)
        self.assertEqual(reasons(found), ["missing_in_b"])
        self.assertEqual(found[0].record_id, "REC-1")
        self.assertEqual(found[0].a_org, "ORG-A")

    def test_orphan_entry(self):
        found = compare([a()], [b(), b("E9", ref="REC-999")], ORGS)
        self.assertEqual(reasons(found), ["orphan_entry"])
        self.assertEqual(found[0].entry_ids, ["E9"])

    def test_orphan_entry_when_reference_is_unreadable(self):
        found = compare([a()], [b(), b("E9", ref=None)], ORGS)
        self.assertEqual(reasons(found), ["orphan_entry"])
        self.assertIn("cannot be read", found[0].detail)

    def test_duplicate_entry(self):
        found = compare([a()], [b("E1"), b("E2")], ORGS)
        self.assertEqual(reasons(found), ["duplicate_entry"])
        self.assertEqual(found[0].entry_ids, ["E1", "E2"])

    def test_value_mismatch(self):
        found = compare([a()], [b(value="90.00")], ORGS)
        self.assertEqual(reasons(found), ["value_mismatch"])
        self.assertEqual((found[0].a_value, found[0].b_value), ("100.00", "90.00"))

    def test_value_mismatch_explains_when_b_has_base_instead_of_total(self):
        found = compare([a()], [b(value="80.00")], ORGS)
        self.assertIn("base_value", found[0].detail)

    def test_value_unreadable_blank_in_b(self):
        found = compare([a()], [b(value=None, raw="")], ORGS)
        self.assertEqual(reasons(found), ["value_unreadable"])
        self.assertEqual(found[0].b_value, "(blank)")

    def test_value_unreadable_garbage_in_b_is_not_dropped(self):
        found = compare([a()], [b(value=None, raw="N/A")], ORGS)
        self.assertEqual(reasons(found), ["value_unreadable"])

    def test_location_mismatch(self):
        found = compare([a()], [b(loc="LOC-1")], ORGS)
        self.assertEqual(found, [])
        found = compare([a(loc="LOC-1")], [b(loc="LOC-2")], ORGS)
        self.assertEqual(reasons(found), ["location_mismatch"])
        self.assertEqual((found[0].a_org, found[0].b_org), ("ORG-A", "ORG-B"))

    def test_date_mismatch(self):
        found = compare([a()], [b(day=date(2026, 3, 3))], ORGS)
        self.assertEqual(reasons(found), ["date_mismatch"])

    def test_duplicate_record_in_a(self):
        found = compare([a(row=2), a(row=3)], [b()], ORGS)
        self.assertEqual(reasons(found), ["duplicate_record_in_a"])


class TestNonErrorsAreNotFlagged(TestCase):
    def test_clean_match_produces_nothing(self):
        self.assertEqual(compare([a()], [b()], ORGS), [])

    def test_split_entries_that_sum_to_the_total_are_not_a_disagreement(self):
        # the REC-1055 case: 71950.93 + 107926.39 == 179877.32
        found = compare([a(total="179877.32")],
                        [b("E1", value="71950.93"), b("E2", value="107926.39")], ORGS)
        self.assertEqual(found, [])

    def test_split_that_does_not_sum_is_a_duplicate(self):
        found = compare([a(total="100.00")],
                        [b("E1", value="40.00"), b("E2", value="50.00")], ORGS)
        self.assertIn("duplicate_entry", reasons(found))

    def test_split_still_has_its_location_checked(self):
        found = compare([a(total="100.00")],
                        [b("E1", value="40.00"), b("E2", value="60.00", loc="LOC-2")], ORGS)
        self.assertEqual(reasons(found), ["location_mismatch"])

    def test_values_equal_at_cent_precision_agree(self):
        self.assertEqual(compare([a(total="100.00")], [b(value="100.0")], ORGS), [])

    def test_voided_state_alone_is_not_compared(self):
        # B has no state column, so there is nothing for it to disagree with.
        self.assertEqual(compare([a()], [b()], ORGS), [])
