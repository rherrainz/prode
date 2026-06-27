from datetime import datetime, time, timedelta, timezone as datetime_timezone
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from apps.matches.models import ApiSyncLog, Match
from apps.matches.services.knockout import advance_knockout_match
from apps.teams.models import Team


TEAM_ALIASES = {
    'Cabo Verde': 'Cabo Verde',
    'Cape Verde': 'Cabo Verde',
    'Congo DR': 'Congo DR',
    'Côte d’Ivoire': "Côte d'Ivoire",
    'Côte d`Ivoire': "Côte d'Ivoire",
    'IR Iran': 'IR Iran',
    'Iran': 'IR Iran',
    'Korea Republic': 'Korea Republic',
    'South Korea': 'Korea Republic',
    'Türkiye': 'Türkiye',
    'Turkey': 'Türkiye',
    'United States': 'USA',
    'USA': 'USA',
}


def _base_url():
    return settings.FIFA_API_BASE_URL.rstrip('/')


def _localized_description(values):
    if not values:
        return ''
    english = next((value for value in values if (value.get('Locale') or '').lower().startswith('en')), None)
    return (english or values[0]).get('Description') or ''


def _normalize_team_name(name):
    return TEAM_ALIASES.get(name, name)


def _team_name(team):
    if not team:
        return ''
    return _normalize_team_name(_localized_description(team.get('TeamName')) or team.get('ShortClubName') or '')


def _team_from_fifa(team):
    name = _team_name(team)
    if not name:
        return None
    return Team.objects.filter(name=name).first()


def _score_value(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_kickoff_at(event):
    value = event.get('Date')
    if not value:
        return None
    kickoff_at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if kickoff_at.tzinfo is None:
        kickoff_at = kickoff_at.replace(tzinfo=datetime_timezone.utc)
    return kickoff_at.astimezone(datetime_timezone.utc)


def _match_for_event(event):
    home_team = _team_from_fifa(event.get('Home'))
    away_team = _team_from_fifa(event.get('Away'))
    kickoff_at = _event_kickoff_at(event)
    if home_team and away_team and kickoff_at:
        start_at = kickoff_at - timedelta(days=1)
        end_at = kickoff_at + timedelta(days=1)
        match = (
            Match.objects
            .filter(
                kickoff_at__gte=start_at,
                kickoff_at__lte=end_at,
                home_team=home_team,
                away_team=away_team,
            )
            .order_by('kickoff_at', 'match_number')
            .first()
        )
        if match:
            return match

    match_number = event.get('MatchNumber')
    if match_number:
        match = Match.objects.filter(match_number=match_number).first()
        if match:
            return match

    event_id = event.get('IdMatch')
    if event_id:
        match = Match.objects.filter(external_id=f'fifa:{event_id}').first()
        if match:
            return match

    if not kickoff_at:
        return None

    start_at = kickoff_at - timedelta(hours=3)
    end_at = kickoff_at + timedelta(hours=3)
    candidates = Match.objects.filter(kickoff_at__gte=start_at, kickoff_at__lte=end_at)
    return min(candidates, key=lambda match: abs(match.kickoff_at - kickoff_at), default=None)


def _winner_from_event(event, home_team, away_team):
    winner_id = event.get('Winner')
    if winner_id:
        if event.get('Home') and str(event['Home'].get('IdTeam')) == str(winner_id):
            return home_team
        if event.get('Away') and str(event['Away'].get('IdTeam')) == str(winner_id):
            return away_team
    return None


def _status_from_event(event):
    if _score_value(event.get('HomeTeamScore')) is None or _score_value(event.get('AwayTeamScore')) is None:
        return Match.Status.SCHEDULED
    if event.get('MatchStatus') in (0, 3, 12):
        return Match.Status.FINISHED
    return Match.Status.FINISHED


def _window_for_dates(base_date, days_back, days_forward):
    start_day = base_date - timedelta(days=days_back)
    end_day = base_date + timedelta(days=days_forward + 1)
    return (
        datetime.combine(start_day, time.min, tzinfo=datetime_timezone.utc),
        datetime.combine(end_day, time.min, tzinfo=datetime_timezone.utc),
    )


def _fetch_matches(start_at, end_at):
    query = urlencode({
        'language': settings.FIFA_API_LANGUAGE,
        'idCompetition': settings.FIFA_WORLD_CUP_COMPETITION_ID,
        'idSeason': settings.FIFA_WORLD_CUP_SEASON_ID,
        'from': start_at.isoformat().replace('+00:00', 'Z'),
        'to': end_at.isoformat().replace('+00:00', 'Z'),
        'count': settings.FIFA_API_MATCH_COUNT,
    })
    endpoint = f'{_base_url()}/calendar/matches?{query}'
    request = Request(endpoint, headers={'User-Agent': 'worldcup-prode/1.0'})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))
    return endpoint, payload.get('Results') or []


def _update_fixture_from_event(match, event, home_team, away_team, dry_run=False):
    external_id = f"fifa:{event.get('IdMatch')}" if event.get('IdMatch') else match.external_id
    kickoff_at = _event_kickoff_at(event) or match.kickoff_at
    stadium = event.get('Stadium') or {}
    venue = _localized_description(stadium.get('Name')) or match.venue
    changed = (
        match.external_id != external_id
        or match.kickoff_at != kickoff_at
        or match.venue != venue
    )
    if home_team:
        changed = changed or match.home_team_id != home_team.id or match.home_team_placeholder != ''
    if away_team:
        changed = changed or match.away_team_id != away_team.id or match.away_team_placeholder != ''
    if dry_run or not changed:
        return changed

    match.external_id = external_id
    match.kickoff_at = kickoff_at
    match.venue = venue
    match.last_synced_at = timezone.now()
    update_fields = [
        'external_id',
        'kickoff_at',
        'venue',
        'last_synced_at',
        'updated_at',
    ]
    if home_team:
        match.home_team = home_team
        match.home_team_placeholder = ''
        update_fields.extend(['home_team', 'home_team_placeholder'])
    if away_team:
        match.away_team = away_team
        match.away_team_placeholder = ''
        update_fields.extend(['away_team', 'away_team_placeholder'])
    match.save(update_fields=update_fields)
    return True


def _update_result_from_event(match, event, home_team, away_team, dry_run=False):
    home_score = _score_value(event.get('HomeTeamScore'))
    away_score = _score_value(event.get('AwayTeamScore'))
    if home_score is None or away_score is None:
        return False

    winner = _winner_from_event(event, home_team, away_team)
    if not winner:
        if home_score > away_score:
            winner = home_team
        elif away_score > home_score:
            winner = away_team

    if dry_run:
        return True

    match.home_score = home_score
    match.away_score = away_score
    match.winner = winner
    match.status = _status_from_event(event)
    match.last_synced_at = timezone.now()
    match.save(update_fields=[
        'home_score',
        'away_score',
        'winner',
        'status',
        'last_synced_at',
        'updated_at',
    ])
    advance_knockout_match(match)
    return True


def sync_fixture(days_back=1, days_forward=7, base_date=None, dry_run=False, update_results=False, only_missing_results=False):
    base_date = base_date or timezone.localdate()
    start_at, end_at = _window_for_dates(base_date, days_back, days_forward)
    endpoint, events = _fetch_matches(start_at, end_at)
    request_count = 1
    fixture_updated_count = 0
    updated_count = 0
    messages = []

    for event in events:
        match = _match_for_event(event)
        if not match:
            messages.append(f"No se encontró partido FIFA #{event.get('MatchNumber') or event.get('IdMatch')}")
            continue
        home_team = _team_from_fifa(event.get('Home')) or match.home_team
        away_team = _team_from_fifa(event.get('Away')) or match.away_team
        if not home_team and not away_team:
            messages.append(f"No se encontraron equipos FIFA para partido {match.match_number}")
            continue
        if _update_fixture_from_event(match, event, home_team, away_team, dry_run=dry_run):
            fixture_updated_count += 1
        if update_results:
            if not home_team or not away_team:
                continue
            if only_missing_results and match.status == Match.Status.FINISHED and match.has_result:
                continue
            if _update_result_from_event(match, event, home_team, away_team, dry_run=dry_run):
                updated_count += 1

    status = 'dry-run' if dry_run else 'ok'
    message = f'Eventos vistos: {len(events)}. Fixture actualizado: {fixture_updated_count}. Resultados actualizados: {updated_count}.'
    if messages:
        message = f'{message} ' + ' | '.join(messages[:5])
    log = ApiSyncLog.objects.create(
        provider='fifa',
        endpoint=endpoint,
        status=status,
        request_count=request_count,
        response_code=200,
        message=message,
    )
    return {
        'log': log,
        'request_count': request_count,
        'seen_count': len(events),
        'updated_count': updated_count,
        'fixture_updated_count': fixture_updated_count,
        'messages': messages,
    }
