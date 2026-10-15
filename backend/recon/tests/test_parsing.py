from datetime import date
from decimal import Decimal as D
from unittest import TestCase

from recon.parsing import normalise_ref, parse_amount, parse_date


class TestNormaliseRef(TestCase):
    def test_every_dirty_spelling_in_the_data_resolves(self):
        for raw in ["REC-1034", "rec1034", "1034", " REC - 1034 ", "Rec-1034"]:
            self.assertEqual(normalise_ref(raw), "REC-1034", raw)

    def test_unreadable_is_none_not_a_guess(self):
        for raw in ["", "   ", "ENT-5", "REC-", "REC-12A", None]:
            self.assertIsNone(normalise_ref(raw), raw)


class TestParseAmount(TestCase):
    def test_plain_and_grouped(self):
        self.assertEqual(parse_amount("88969.92"), D("88969.92"))
        self.assertEqual(parse_amount("1,25,400.00"), D("125400.00"))   # Indian grouping
        self.assertEqual(parse_amount("125,400.00"), D("125400.00"))    # Western grouping
        self.assertEqual(parse_amount(" 12.50 "), D("12.50"))

    def test_unparseable_is_none(self):
        for raw in ["", "  ", "abc", "N/A", "1,5", "12..5", "NaN", None]:
            self.assertIsNone(parse_amount(raw), raw)


class TestParseDate(TestCase):
    def test_iso_ok_everything_else_none(self):
        self.assertEqual(parse_date("2026-03-31"), date(2026, 3, 31))
        for raw in ["", "31/03/2026", "2026-13-40", None]:
            self.assertIsNone(parse_date(raw), raw)
