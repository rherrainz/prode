from datetime import date

from django.core.management.base import BaseCommand

from apps.matches.services.thesportsdb import sync_results
from apps.predictions.services import recalculate_predictions


class Command(BaseCommand):
    help = 'Sync World Cup results from TheSportsDB and recalculate prediction points.'

    def add_arguments(self, parser):
        parser.add_argument('--date', help='Base date in YYYY-MM-DD format. Defaults to today.')
        parser.add_argument('--days-back', type=int, default=1)
        parser.add_argument('--days-forward', type=int, default=1)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        base_date = date.fromisoformat(options['date']) if options['date'] else None
        result = sync_results(
            days_back=options['days_back'],
            days_forward=options['days_forward'],
            base_date=base_date,
            dry_run=options['dry_run'],
        )
        recalculated_count = 0
        if not options['dry_run']:
            recalculated_count = recalculate_predictions()

        self.stdout.write(self.style.SUCCESS(
            f"TheSportsDB sync: {result['request_count']} requests, "
            f"{result['seen_count']} eventos, {result['updated_count']} actualizaciones. "
            f"Pronósticos recalculados: {recalculated_count}."
        ))
