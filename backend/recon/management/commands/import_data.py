from pathlib import Path

from django.core.management.base import BaseCommand

from recon.importer import run_import

DEFAULT_DIR = Path(__file__).resolve().parents[4] / "data"


class Command(BaseCommand):
    help = "Load locations.csv, system_a.csv, system_b.csv and compute disagreements (replaces existing data)."

    def add_arguments(self, parser):
        parser.add_argument("data_dir", nargs="?", default=str(DEFAULT_DIR))

    def handle(self, *args, data_dir, **opts):
        s = run_import(data_dir)
        self.stdout.write(f"locations: {s.locations}")
        self.stdout.write(f"system A: read {s.a_rows_read}, stored {s.a_rows_stored}")
        self.stdout.write(f"system B: read {s.b_rows_read}, stored {s.b_rows_stored}")
        self.stdout.write(f"disagreements: {s.findings}")
        for reason, n in sorted(s.findings_by_reason.items()):
            self.stdout.write(f"  {reason}: {n}")
        if s.quarantined:
            self.stdout.write(self.style.WARNING(
                f"{s.quarantined} finding(s) belong to no known org and are visible to NO tenant"))
