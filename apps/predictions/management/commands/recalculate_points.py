from django.core.management.base import BaseCommand, CommandError

from apps.matches.models import Match
from apps.predictions.services import recalculate_predictions
from apps.tournaments.models import FriendTournament


class Command(BaseCommand):
    help = 'Recalculate prediction points for all predictions, or filtered by tournament slug or match id.'

    def add_arguments(self, parser):
        parser.add_argument('--tournament', help='Tournament slug')
        parser.add_argument('--match', type=int, help='Match id')

    def handle(self, *args, **options):
        tournament = None
        match = None
        if options['tournament']:
            try:
                tournament = FriendTournament.objects.get(slug=options['tournament'])
            except FriendTournament.DoesNotExist as exc:
                raise CommandError('Tournament not found.') from exc
        if options['match']:
            try:
                match = Match.objects.get(pk=options['match'])
            except Match.DoesNotExist as exc:
                raise CommandError('Match not found.') from exc
        count = recalculate_predictions(tournament=tournament, match=match)
        self.stdout.write(self.style.SUCCESS(f'Se recalcularon {count} pronósticos.'))
