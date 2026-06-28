from datetime import datetime, time, timedelta, timezone as datetime_timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.matches.models import ApiSyncLog, Match
from apps.matches.services.fifa import sync_fixture
from apps.matches.services.knockout import advance_knockout_match
from apps.teams.models import Team


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

PROVIDER_TEAM_ALIASES = {
    'Bosnia and Herzegovina': 'Bosnia-Herzegovina',
    'Cabo Verde': 'Cape Verde',
    'Congo DR': 'DR Congo',
    'Czechia': 'Czech Republic',
    'IR Iran': 'Iran',
    "Côte d'Ivoire": 'Ivory Coast',
    'Korea Republic': 'South Korea',
    'Türkiye': 'Turkey',
}

EVENT_DATE_TIMEZONE = ZoneInfo('America/New_York')


def _base_url():
    return f'{settings.THESPORTSDB_BASE_URL.rstrip("/")}/{settings.THESPORTSDB_API_KEY}'


def _normalize_team_name(name):
    return TEAM_ALIASES.get(name, name)


def _provider_team_name(name):
    return PROVIDER_TEAM_ALIASES.get(name, name)


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


def _fetch_events_by_name(home_name, away_name):
    event_name = f'{_provider_team_name(home_name)}_vs_{_provider_team_name(away_name)}'.replace(' ', '_')
    query = urlencode({'e': event_name})
    endpoint = f'{_base_url()}/searchevents.php?{query}'
    request = Request(endpoint, headers={'User-Agent': 'worldcup-prode/1.0'})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))
    return endpoint, payload.get('event') or payload.get('events') or []


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


def _sync_window(days):
    start_day = min(days)
    end_day = max(days) + timedelta(days=1)
    start_at = datetime.combine(start_day, time.min, tzinfo=datetime_timezone.utc)
    end_at = datetime.combine(end_day, time.min, tzinfo=datetime_timezone.utc)
    return start_at, end_at


def _event_date(event):
    value = event.get('dateEvent')
    if not value:
        return None
    return datetime.fromisoformat(value).date()


def _event_kickoff_at(event):
    timestamp = event.get('strTimestamp')
    if timestamp:
        value = timestamp.replace('Z', '+00:00')
        event_time = datetime.fromisoformat(value)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=datetime_timezone.utc)
        return event_time.astimezone(datetime_timezone.utc)

    event_date = event.get('dateEvent')
    event_time = event.get('strTime')
    if not event_date or not event_time:
        return None

    time_value = event_time.split('+', 1)[0]
    parsed_time = time.fromisoformat(time_value)
    return datetime.combine(datetime.fromisoformat(event_date).date(), parsed_time, tzinfo=datetime_timezone.utc)


def _event_key(event):
    event_id = event.get('idEvent')
    if event_id:
        return f'id:{event_id}'
    return ':'.join([
        event.get('dateEvent') or '',
        event.get('strHomeTeam') or '',
        event.get('strAwayTeam') or '',
    ])


def _event_is_finished(event):
    status = (event.get('strStatus') or '').strip().lower()
    if not status:
        return event.get('intHomeScore') not in (None, '') and event.get('intAwayScore') not in (None, '')
    return status in {'ft', 'aet', 'pen', 'match finished', 'finished'}


def _event_sync_priority(event):
    has_score = event.get('intHomeScore') not in (None, '') and event.get('intAwayScore') not in (None, '')
    if _event_is_finished(event) and has_score:
        return 3
    if has_score:
        return 2
    return 1


def _store_event(collected_events, key, day, event):
    existing = collected_events.get(key)
    if not existing or _event_sync_priority(event) > _event_sync_priority(existing[1]):
        collected_events[key] = (day, event)


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
    ) or _knockout_match_for_event(event)


def _knockout_match_for_event(event):
    kickoff_at = _event_kickoff_at(event)
    if not kickoff_at:
        return None

    start_at = kickoff_at - timedelta(hours=3)
    end_at = kickoff_at + timedelta(hours=3)
    candidates = (
        Match.objects
        .filter(
            phase__in=[
                Match.Phase.ROUND_OF_32,
                Match.Phase.ROUND_OF_16,
                Match.Phase.QUARTER_FINAL,
                Match.Phase.SEMI_FINAL,
                Match.Phase.THIRD_PLACE,
                Match.Phase.FINAL,
            ],
            kickoff_at__gte=start_at,
            kickoff_at__lte=end_at,
        )
        .order_by('kickoff_at', 'match_number')
    )
    return min(candidates, key=lambda match: abs(match.kickoff_at - kickoff_at), default=None)


def _team_from_event_name(name):
    normalized_name = _normalize_team_name(name or '')
    if not normalized_name:
        return None
    return Team.objects.filter(name=normalized_name).first()


def _score_value(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _penalty_score(event, side):
    keys = [
        f'int{side}PenaltyScore',
        f'int{side}Penalties',
        f'int{side}Penalty',
        f'str{side}PenaltyScore',
        f'str{side}Penalties',
    ]
    for key in keys:
        value = _score_value(event.get(key))
        if value is not None:
            return value
    return None


def _winner_from_event(event, home_score, away_score, home_team, away_team):
    if home_score > away_score:
        return home_team
    if away_score > home_score:
        return away_team

    home_penalties = _penalty_score(event, 'Home')
    away_penalties = _penalty_score(event, 'Away')
    if home_penalties is not None and away_penalties is not None:
        if home_penalties > away_penalties:
            return home_team
        if away_penalties > home_penalties:
            return away_team

    winner_name = (
        event.get('strWinner')
        or event.get('strWinningTeam')
        or event.get('strWinnerTeam')
        or event.get('strResultWinner')
    )
    winner = _team_from_event_name(winner_name)
    if winner and winner in {home_team, away_team}:
        return winner
    return None


def _sync_event_fixture(match, event, home_team, away_team, dry_run=False):
    external_id = f"thesportsdb:{event.get('idEvent')}" if event.get('idEvent') else match.external_id
    changed = (
        match.external_id != external_id
        or match.home_team_id != home_team.id
        or match.away_team_id != away_team.id
        or match.home_team_placeholder != ''
        or match.away_team_placeholder != ''
    )
    if dry_run or not changed:
        return changed

    match.external_id = external_id
    match.home_team = home_team
    match.away_team = away_team
    match.home_team_placeholder = ''
    match.away_team_placeholder = ''
    match.last_synced_at = timezone.now()
    match.save(update_fields=[
        'external_id',
        'home_team',
        'away_team',
        'home_team_placeholder',
        'away_team_placeholder',
        'last_synced_at',
        'updated_at',
    ])
    return True


def sync_results(days_back=1, days_forward=1, base_date=None, dry_run=False, use_fifa_fallback=True):
    base_date = base_date or timezone.localdate()
    request_count = 0
    updated_count = 0
    fixture_updated_count = 0
    seen_count = 0
    messages = []
    collected_events = {}

    days = _sync_days(base_date, days_back, days_forward)
    sync_day_set = set(days)
    start_at, end_at = _sync_window(days)

    for day in days:
        endpoint, day_events = _fetch_events_for_day(day)
        request_count += 1
        for event in day_events:
            key = _event_key(event)
            _store_event(collected_events, key, day, event)

    endpoint, season_events = _fetch_events_for_season()
    request_count += 1
    for event in season_events:
        if _event_date(event) not in sync_day_set:
            continue
        key = _event_key(event)
        _store_event(collected_events, key, _event_date(event), event)

    expected_matches = (
        Match.objects
        .filter(kickoff_at__gte=start_at, kickoff_at__lt=end_at, home_team__isnull=False, away_team__isnull=False)
        .select_related('home_team', 'away_team')
    )
    for expected_match in expected_matches:
        endpoint, searched_events = _fetch_events_by_name(expected_match.home_team.name, expected_match.away_team.name)
        request_count += 1
        for event in searched_events:
            if _event_date(event) not in sync_day_set:
                continue
            key = _event_key(event)
            _store_event(collected_events, key, _event_date(event), event)

    seen_count = len(collected_events)
    for day, event in collected_events.values():
        match = _match_for_event(event)
        if not match:
            messages.append(f"No se encontró partido para {event.get('strHomeTeam')} vs {event.get('strAwayTeam')} ({day})")
            continue
        home_team = _team_from_event_name(event.get('strHomeTeam')) or match.home_team
        away_team = _team_from_event_name(event.get('strAwayTeam')) or match.away_team
        if not home_team or not away_team:
            messages.append(f"No se encontraron equipos para {event.get('strHomeTeam')} vs {event.get('strAwayTeam')} ({day})")
            continue
        if _sync_event_fixture(match, event, home_team, away_team, dry_run=dry_run):
            fixture_updated_count += 1

        home_score = _score_value(event.get('intHomeScore'))
        away_score = _score_value(event.get('intAwayScore'))
        if home_score is None or away_score is None:
            continue
        if not _event_is_finished(event):
            continue

        winner = _winner_from_event(event, home_score, away_score, home_team, away_team)
        if match.phase != Match.Phase.GROUP_STAGE and home_score == away_score and not winner:
            messages.append(f"No se encontró ganador por penales para {event.get('strHomeTeam')} vs {event.get('strAwayTeam')} ({day})")
        if dry_run:
            updated_count += 1
            continue
        match.external_id = f"thesportsdb:{event.get('idEvent')}" if event.get('idEvent') else match.external_id
        match.home_team = home_team
        match.away_team = away_team
        match.home_team_placeholder = ''
        match.away_team_placeholder = ''
        match.home_score = home_score
        match.away_score = away_score
        match.winner = winner
        match.status = Match.Status.FINISHED
        match.last_synced_at = timezone.now()
        match.save(update_fields=[
            'external_id',
            'home_team',
            'away_team',
            'home_team_placeholder',
            'away_team_placeholder',
            'home_score',
            'away_score',
            'winner',
            'status',
            'last_synced_at',
            'updated_at',
        ])
        updated_count += 1
        fixture_updated_count += advance_knockout_match(match)

    fifa_result = None
    if use_fifa_fallback:
        fifa_result = sync_fixture(
            days_back=days_back,
            days_forward=days_forward,
            base_date=base_date,
            dry_run=dry_run,
            update_results=True,
            only_missing_results=True,
        )
        request_count += fifa_result['request_count']
        seen_count += fifa_result['seen_count']
        updated_count += fifa_result['updated_count']
        fixture_updated_count += fifa_result['fixture_updated_count']
        messages.extend(fifa_result['messages'])

    status = 'dry-run' if dry_run else 'ok'
    message = f'Eventos vistos: {seen_count}. Partidos actualizados: {updated_count}. Fixture actualizado: {fixture_updated_count}.'
    if messages:
        message = f'{message} ' + ' | '.join(messages[:5])
    log = ApiSyncLog.objects.create(
        provider='thesportsdb',
        endpoint='eventsday/eventsseason/searchevents',
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
        'fixture_updated_count': fixture_updated_count,
        'messages': messages,
        'fifa_result': fifa_result,
    }
