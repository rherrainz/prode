from django.core.management.base import BaseCommand

from apps.matches.services.api_football import sync_fixtures_stub


class Command(BaseCommand):
    help = 'Run the API-Football sync stub and create an ApiSyncLog entry.'

    def handle(self, *args, **options):
        log = sync_fixtures_stub()
        self.stdout.write(self.style.SUCCESS(f'Sync stub registrado: {log.id}'))
