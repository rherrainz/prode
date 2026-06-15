from django.db.models import Q

from apps.tournaments.models import FriendTournament
from apps.tournaments.services import update_leaderboard_positions

from .models import Prediction


def recalculate_predictions(tournament=None, match=None):
    queryset = Prediction.objects.select_related('match')
    if tournament:
        queryset = queryset.filter(tournament=tournament)
    if match:
        queryset = queryset.filter(match=match)
    count = 0
    changed_tournament_ids = set()
    for prediction in queryset.filter(Q(match__status='finished')):
        old_points = prediction.points
        old_calculated_at = prediction.calculated_at
        prediction.calculate_points(save=True)
        if old_points != prediction.points or (old_calculated_at is None and prediction.calculated_at is not None):
            changed_tournament_ids.add(prediction.tournament_id)
        count += 1
    for changed_tournament in FriendTournament.objects.filter(pk__in=changed_tournament_ids):
        update_leaderboard_positions(changed_tournament)
    return count
