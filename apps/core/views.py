from django.shortcuts import render
from django.utils import timezone

from apps.matches.models import Match


def home(request):
    upcoming_matches = (
        Match.objects.filter(kickoff_at__gte=timezone.now())
        .select_related('home_team', 'away_team', 'group')
        .order_by('kickoff_at', 'match_number')[:10]
    )
    return render(request, 'core/home.html', {'upcoming_matches': upcoming_matches})

# Create your views here.
