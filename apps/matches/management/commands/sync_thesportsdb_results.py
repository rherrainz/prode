from datetime import date

from django.core.management.base import BaseCommand

from apps.matches.services.thesportsdb import sync_results


class Command(BaseCommand):
    help = 'Sync final World Cup match results from TheSportsDB into the local database.'

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
        self.stdout.write(self.style.SUCCESS(
            f"TheSportsDB sync: {result['request_count']} requests, "
            f"{result['seen_count']} eventos, {result['updated_count']} actualizaciones."
        ))
