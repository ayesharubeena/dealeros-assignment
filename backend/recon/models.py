from django.db import models


class Location(models.Model):
    """locations.csv -- the ONLY place the location -> org (tenant) mapping exists."""
    location_id = models.CharField(max_length=32, primary_key=True)
    org_id = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)


class SystemARecord(models.Model):
    """One row of system_a.csv. Raw text is kept next to every parsed value."""
    row_number = models.PositiveIntegerField()          # line in the CSV (header = 1)
    record_id = models.CharField(max_length=64, db_index=True)   # NOT unique: dirty data
    location_id = models.CharField(max_length=32, blank=True)
    event_date = models.DateField(null=True)
    category_code = models.CharField(max_length=32, blank=True)
    actor_id = models.CharField(max_length=32, blank=True)       # may be blank
    base_value = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    adjustment = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    raw_total_value = models.CharField(max_length=64, blank=True)
    state = models.CharField(max_length=32, blank=True)


class SystemBEntry(models.Model):
    """One row of system_b.csv."""
    row_number = models.PositiveIntegerField()
    entry_id = models.CharField(max_length=64, db_index=True)
    raw_ref = models.CharField(max_length=64, blank=True)        # exactly as exported
    record_ref = models.CharField(max_length=64, blank=True, db_index=True)  # normalised; '' = unreadable
    location_id = models.CharField(max_length=32, blank=True)
    recorded_on = models.DateField(null=True)
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    raw_value = models.CharField(max_length=64, blank=True)      # '1,25,400.00', '' ...
    label = models.CharField(max_length=128, blank=True)


class Disagreement(models.Model):
    """Materialised output of compare(). Rebuilt on every import.

    a_org / b_org are the tenants that own each side's location. A viewer may
    see a row only if it is THEIR org on at least one side, and only sees
    their own side's data (see views.serialise).
    """
    reason = models.CharField(max_length=32, db_index=True)
    record_id = models.CharField(max_length=64, blank=True)
    entry_ids = models.JSONField(default=list)
    a_value = models.CharField(max_length=64, blank=True)
    b_value = models.CharField(max_length=64, blank=True)
    a_location = models.CharField(max_length=32, blank=True)
    b_location = models.CharField(max_length=32, blank=True)
    a_org = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    b_org = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    sort_value = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    detail = models.TextField(blank=True)
