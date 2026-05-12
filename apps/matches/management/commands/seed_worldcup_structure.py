from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.matches.models import Match
from apps.teams.models import Team, WorldCupGroup


GROUPS = {
    'A': ['Mexico', 'South Africa', 'Korea Republic', 'Czechia'],
    'B': ['Canada', 'Bosnia and Herzegovina', 'Qatar', 'Switzerland'],
    'C': ['Brazil', 'Morocco', 'Haiti', 'Scotland'],
    'D': ['USA', 'Paraguay', 'Australia', 'Türkiye'],
    'E': ['Germany', 'Curaçao', "Côte d'Ivoire", 'Ecuador'],
    'F': ['Netherlands', 'Japan', 'Sweden', 'Tunisia'],
    'G': ['Belgium', 'Egypt', 'IR Iran', 'New Zealand'],
    'H': ['Spain', 'Cabo Verde', 'Saudi Arabia', 'Uruguay'],
    'I': ['France', 'Senegal', 'Iraq', 'Norway'],
    'J': ['Argentina', 'Algeria', 'Austria', 'Jordan'],
    'K': ['Portugal', 'Congo DR', 'Uzbekistan', 'Colombia'],
    'L': ['England', 'Croatia', 'Ghana', 'Panama'],
}

VENUES = [
    ('Mexico City Stadium', 'America/Mexico_City'),
    ('Estadio Guadalajara', 'America/Mexico_City'),
    ('Toronto Stadium', 'America/Toronto'),
    ('Los Angeles Stadium', 'America/Los_Angeles'),
    ('Boston Stadium', 'America/New_York'),
    ('BC Place Vancouver', 'America/Vancouver'),
    ('New York New Jersey Stadium', 'America/New_York'),
    ('San Francisco Bay Area Stadium', 'America/Los_Angeles'),
    ('Seattle Stadium', 'America/Los_Angeles'),
    ('Dallas Stadium', 'America/Chicago'),
    ('Houston Stadium', 'America/Chicago'),
    ('Kansas City Stadium', 'America/Chicago'),
    ('Atlanta Stadium', 'America/New_York'),
    ('Miami Stadium', 'America/New_York'),
    ('Philadelphia Stadium', 'America/New_York'),
    ('Monterrey Stadium', 'America/Mexico_City'),
]

GROUP_PAIRINGS = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]
GROUP_LOCAL_TIMES = [
    (2026, 6, 11, 13, 0),
    (2026, 6, 11, 19, 0),
    (2026, 6, 12, 15, 0),
    (2026, 6, 12, 18, 0),
]


def aware_from_local(year, month, day, hour, minute, tz_name):
    local_dt = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(ZoneInfo('UTC'))


class Command(BaseCommand):
    help = 'Seed drawn World Cup 2026 groups, teams, 72 group-stage fixtures, and knockout placeholders up to 104 matches.'

    def handle(self, *args, **options):
        groups = []
        for index, (letter, team_names) in enumerate(GROUPS.items(), start=1):
            group, _ = WorldCupGroup.objects.update_or_create(
                name=f'Group {letter}',
                defaults={'order': index},
            )
            groups.append((letter, group))
            for position, team_name in enumerate(team_names, start=1):
                Team.objects.update_or_create(
                    fifa_code=f'{letter}{position}',
                    defaults={'name': team_name, 'group': group},
                )

        match_number = 1
        for group_index, (letter, group) in enumerate(groups):
            teams = [Team.objects.get(fifa_code=f'{letter}{position}') for position in range(1, 5)]
            round_offsets = [0, 7, 13]
            for pairing_index, (home_idx, away_idx) in enumerate(GROUP_PAIRINGS):
                venue, venue_timezone = VENUES[(match_number - 1) % len(VENUES)]
                base_year, base_month, base_day, base_hour, base_minute = GROUP_LOCAL_TIMES[(match_number - 1) % len(GROUP_LOCAL_TIMES)]
                round_number = pairing_index // 2
                kickoff_at = aware_from_local(
                    base_year,
                    base_month,
                    base_day,
                    base_hour,
                    base_minute,
                    venue_timezone,
                ) + timedelta(days=group_index + round_offsets[round_number])
                Match.objects.update_or_create(
                    match_number=match_number,
                    defaults={
                        'phase': Match.Phase.GROUP_STAGE,
                        'group': group,
                        'home_team': teams[home_idx],
                        'away_team': teams[away_idx],
                        'home_team_placeholder': '',
                        'away_team_placeholder': '',
                        'kickoff_at': kickoff_at,
                        'venue': venue,
                        'venue_timezone': venue_timezone,
                    },
                )
                match_number += 1

        phases = (
            [(Match.Phase.ROUND_OF_32, 16)]
            + [(Match.Phase.ROUND_OF_16, 8)]
            + [(Match.Phase.QUARTER_FINAL, 4)]
            + [(Match.Phase.SEMI_FINAL, 2)]
            + [(Match.Phase.THIRD_PLACE, 1)]
            + [(Match.Phase.FINAL, 1)]
        )
        slot = 1
        knockout_start = datetime(2026, 6, 28, 15, 0)
        for phase, amount in phases:
            for phase_index in range(amount):
                venue, venue_timezone = VENUES[(match_number - 1) % len(VENUES)]
                day_offset = slot // 4
                if phase == Match.Phase.FINAL:
                    venue = 'New York New Jersey Stadium'
                    venue_timezone = 'America/New_York'
                    kickoff_at = aware_from_local(2026, 7, 19, 15, 0, venue_timezone)
                elif phase == Match.Phase.THIRD_PLACE:
                    venue = 'Miami Stadium'
                    venue_timezone = 'America/New_York'
                    kickoff_at = aware_from_local(2026, 7, 18, 17, 0, venue_timezone)
                else:
                    local_dt = knockout_start + timedelta(days=day_offset, hours=(phase_index % 3) * 3)
                    kickoff_at = aware_from_local(local_dt.year, local_dt.month, local_dt.day, local_dt.hour, local_dt.minute, venue_timezone)
                Match.objects.update_or_create(
                    match_number=match_number,
                    defaults={
                        'phase': phase,
                        'group': None,
                        'home_team': None,
                        'away_team': None,
                        'home_team_placeholder': f'{phase.replace("_", " ").title()} equipo local {slot}',
                        'away_team_placeholder': f'{phase.replace("_", " ").title()} equipo visitante {slot}',
                        'kickoff_at': kickoff_at,
                        'venue': venue,
                        'venue_timezone': venue_timezone,
                    },
                )
                match_number += 1
                slot += 1

        self.stdout.write(self.style.SUCCESS('Estructura sembrada: 12 grupos sorteados, 48 equipos, 104 partidos con zona horaria de sede.'))
