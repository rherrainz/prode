from datetime import datetime, time, timedelta, timezone as datetime_timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
from zoneinfo import ZoneInfo

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

EVENT_DATE_TIMEZONE = ZoneInfo('America/New_York')


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


def _fetch_events_for_season():
    query = urlencode({
        'id': settings.THESPORTSDB_WORLD_CUP_LEAGUE_ID,
        's': settings.THESPORTSDB_WORLD_CUP_SEASON,
    })
    endpoint = f'{_base_url()}/eventsseason.php?{query}'
    request = Request(endpoint, headers={'User-Agent': 'worldcup-prode/1.0'})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))
    return endpoint, payload.get('events') or []


def _sync_days(base_date, days_back, days_forward):
    days = {base_date + timedelta(days=offset) for offset in range(-days_back, days_forward + 1)}
    start_day = min(days)
    end_day = max(days) + timedelta(days=1)
    start_at = datetime.combine(start_day, time.min, tzinfo=datetime_timezone.utc)
    end_at = datetime.combine(end_day, time.min, tzinfo=datetime_timezone.utc)

    for match in Match.objects.filter(kickoff_at__gte=start_at, kickoff_at__lt=end_at).only('kickoff_at'):
        days.add(match.kickoff_at.astimezone(EVENT_DATE_TIMEZONE).date())

    return sorted(days)


def _event_date(event):
    value = event.get('dateEvent')
    if not value:
        return None
    return datetime.fromisoformat(value).date()


def _event_key(event):
    event_id = event.get('idEvent')
    if event_id:
        return f'id:{event_id}'
    return ':'.join([
        event.get('dateEvent') or '',
        event.get('strHomeTeam') or '',
        event.get('strAwayTeam') or '',
    ])


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
    collected_events = []
    seen_event_keys = set()

    days = _sync_days(base_date, days_back, days_forward)
    sync_day_set = set(days)

    for day in days:
        endpoint, day_events = _fetch_events_for_day(day)
        request_count += 1
        for event in day_events:
            key = _event_key(event)
            if key not in seen_event_keys:
                seen_event_keys.add(key)
                collected_events.append((day, event))

    endpoint, season_events = _fetch_events_for_season()
    request_count += 1
    for event in season_events:
        if _event_date(event) not in sync_day_set:
            continue
        key = _event_key(event)
        if key not in seen_event_keys:
            seen_event_keys.add(key)
            collected_events.append((_event_date(event), event))

    seen_count = len(collected_events)
    for day, event in collected_events:
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
        endpoint='eventsday/eventsseason',
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
