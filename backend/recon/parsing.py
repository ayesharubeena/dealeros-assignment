"""Pure functions that turn dirty CSV strings into clean values.

Rule for all of them: never raise, never guess. If a value can't be read
unambiguously we return None and the caller decides what to do with that.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# "125400", "125400.50", "1,25,400.00" (Indian grouping), "125,400.00" (Western).
# Deliberately NOT accepted: "1,5" -- is that 1.5 or 15? We refuse to guess.
_AMOUNT_RE = re.compile(r"^-?(\d+|\d{1,3}(,\d{2,3})+)(\.\d+)?$")
_REF_RE = re.compile(r"^(?:REC-?)?(\d+)$")


def parse_amount(raw):
    """'1,25,400.00' -> Decimal('125400.00'); '' / 'abc' / '1,5' -> None."""
    if raw is None:
        return None
    text = raw.strip()
    if not _AMOUNT_RE.match(text):
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:  # pragma: no cover - regex already guards this
        return None


def normalise_ref(raw):
    """'rec1034', ' REC - 1070 ', '1112', 'REC-1001' -> 'REC-1034' etc.

    Returns None when the reference can't be read at all.
    """
    if raw is None:
        return None
    squashed = re.sub(r"\s+", "", raw).upper()
    match = _REF_RE.match(squashed)
    return f"REC-{match.group(1)}" if match else None


def normalise_location(raw):
    return (raw or "").strip().upper() or None


def parse_date(raw):
    """ISO dates only (YYYY-MM-DD). Anything else -> None."""
    try:
        return datetime.strptime((raw or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
