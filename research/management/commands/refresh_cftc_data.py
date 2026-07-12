from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from research.providers import CFTCProvider
from research.services import record_provider_result, serialize_run, store_cftc_positions


class Command(BaseCommand):
    help = "Refresh two years of CFTC TFF Futures Only positions."

    def handle(self, *args, **options):
        provider = CFTCProvider()
        try:
            result = provider.positions(
                report_type="tff-futures",
                start_date=f"{max(timezone.now().year - 2, 2000)}-01-01",
            )
            run = record_provider_result(result, persist=store_cftc_positions)
        finally:
            provider.close()
        self.stdout.write(str(serialize_run(run)))
        if run.status == "failed":
            self.stderr.write(self.style.ERROR(run.error))
        else:
            self.stdout.write(self.style.SUCCESS("CFTC refresh completed"))
