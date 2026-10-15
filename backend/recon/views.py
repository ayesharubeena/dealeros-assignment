"""Read API. THE tenant boundary lives in `visible_to()` -- every query goes through it."""
from django.db.models import Count, Q
from django.http import JsonResponse

from .compare import REASONS
from .models import Disagreement, Location

ORDERINGS = {"value": "sort_value", "-value": "-sort_value"}


def visible_to(org):
    """A row is visible to `org` only if `org` owns the A side or the B side."""
    return Disagreement.objects.filter(Q(a_org=org) | Q(b_org=org))


def serialise(d, org):
    """Strict rule: a side's data is shown only if THAT side belongs to `org`.
    (A side that does not exist for this reason -- e.g. no A record for an orphan --
    has nothing to hide.) A cross-org mismatch therefore shows each tenant only its
    own half, and a side with an unknown owner is never shown to anyone."""
    a_exists = d.reason != "orphan_entry"
    b_exists = d.reason != "missing_in_b"
    a_ok, b_ok = d.a_org == org, d.b_org == org
    redacted = (a_exists and not a_ok) or (b_exists and not b_ok)
    return {
        "id": d.id,
        "reason": d.reason,
        # for an orphan the "record id" is B's own reference, so B's owner may see it
        "record_id": d.record_id if (a_ok or (not a_exists and b_ok)) else "",
        "entry_ids": d.entry_ids if b_ok else [],
        "a_value": d.a_value if a_ok else "",
        "b_value": d.b_value if b_ok else "",
        "a_location": d.a_location if a_ok else "",
        "b_location": d.b_location if b_ok else "",
        "sort_value": str(d.sort_value) if (d.sort_value is not None and (a_ok or not a_exists)) else None,
        "detail": "Other side belongs to a different org and is hidden" if redacted else d.detail,
        "redacted": redacted,
    }


def orgs(request):
    ids = sorted(Location.objects.values_list("org_id", flat=True).distinct())
    return JsonResponse({"orgs": ids})


def disagreements(request):
    org = request.GET.get("org", "").strip()
    if not org:
        return JsonResponse({"error": "org is required"}, status=400)
    if not Location.objects.filter(org_id=org).exists():
        return JsonResponse({"error": "unknown org"}, status=404)

    base = visible_to(org)
    counts = dict(base.values_list("reason").annotate(n=Count("id")))   # counts ignore the reason filter

    qs = base
    reason = request.GET.get("reason", "").strip()
    if reason:
        qs = qs.filter(reason=reason)
    qs = qs.order_by(ORDERINGS.get(request.GET.get("ordering", ""), "id"), "id")

    return JsonResponse({
        "org": org,
        "reasons": [{"key": k, "label": label, "count": counts.get(k, 0)} for k, label in REASONS],
        "results": [serialise(d, org) for d in qs],
    })
