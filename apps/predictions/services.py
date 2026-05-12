from django.db.models import Q

from .models import Prediction


def recalculate_predictions(tournament=None, match=None):
    queryset = Prediction.objects.select_related('match')
    if tournament:
        queryset = queryset.filter(tournament=tournament)
    if match:
        queryset = queryset.filter(match=match)
    count = 0
    for prediction in queryset.filter(Q(match__status='finished')):
        prediction.calculate_points(save=True)
        count += 1
    return count
