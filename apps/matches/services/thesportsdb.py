from datetime import timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from django.conf import settings
from django.utils import timezone

from apps.matches.models import ApiSyncLog, Match


TEAM_ALIASES = {
    'Bosnia-Herzegovina': 'Bosnia and Herzegovina',
    'Cape Verde': 'Cabo Verde',
    'Czech Republic': 'Czechia',
    'DR Congo': 'Congo DR',
    'Iran': 'IR Iran',
    'Ivory Coast': "Côte d'Ivoire",
    'South Korea': 'Korea Republic',
    'Turkey': 'Türkiye',
}


def _base_url():
    return f'{settings.THESPORTSDB_BASE_URL.rstrip("/")}/{settings.THESPORTSDB_API_KEY}'


def _normalize_team_name(name):
    return TEAM_ALIASES.get(name, name)


def _fetch_events_for_day(day):
    query = urlencode({
        'd': day.isoformat(),
        'l': settings.THESPORTSDB_WORLD_CUP_LEAGUE_ID,
    })
    endpoint = f'{_base_url()}/eventsday.php?{query}'
    request = Request(endpoint, headers={'User-Agent': 'worldcup-prode/1.0'})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))
    return endpoint, payload.get('events') or []


def _match_for_event(event):
    home_name = _normalize_team_name(event.get('strHomeTeam') or '')
    away_name = _normalize_team_name(event.get('strAwayTeam') or '')
    event_id = event.get('idEvent')
    if event_id:
        match = Match.objects.filter(external_id=f'thesportsdb:{event_id}').first()
        if match:
            return match
    return (
        Match.objects.filter(home_team__name=home_name, away_team__name=away_name)
        .order_by('match_number')
        .first()
    )


def _score_value(value):
    if value in (None, ''):
        return None
    return int(value)


def sync_results(days_back=1, days_forward=1, base_date=None, dry_run=False):
    base_date = base_date or timezone.localdate()
    request_count = 0
    updated_count = 0
    seen_count = 0
    messages = []

    for offset in range(-days_back, days_forward + 1):
        day = base_date + timedelta(days=offset)
        endpoint, events = _fetch_events_for_day(day)
        request_count += 1
        seen_count += len(events)
        for event in events:
            home_score = _score_value(event.get('intHomeScore'))
            away_score = _score_value(event.get('intAwayScore'))
            if home_score is None or away_score is None:
                continue
            match = _match_for_event(event)
            if not match:
                messages.append(f"No se encontró partido para {event.get('strHomeTeam')} vs {event.get('strAwayTeam')} ({day})")
                continue
            if dry_run:
                updated_count += 1
                continue
            match.external_id = f"thesportsdb:{event.get('idEvent')}" if event.get('idEvent') else match.external_id
            match.home_score = home_score
            match.away_score = away_score
            match.status = Match.Status.FINISHED
            match.last_synced_at = timezone.now()
            match.save(update_fields=['external_id', 'home_score', 'away_score', 'status', 'last_synced_at', 'updated_at'])
            updated_count += 1

    status = 'dry-run' if dry_run else 'ok'
    message = f'Eventos vistos: {seen_count}. Partidos actualizados: {updated_count}.'
    if messages:
        message = f'{message} ' + ' | '.join(messages[:5])
    log = ApiSyncLog.objects.create(
        provider='thesportsdb',
        endpoint='eventsday',
        status=status,
        request_count=request_count,
        response_code=200,
        message=message,
    )
    return {
        'log': log,
        'request_count': request_count,
        'seen_count': seen_count,
        'updated_count': updated_count,
        'messages': messages,
    }
