from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
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

FLAG_CODES = {
    'Mexico': 'mx',
    'South Africa': 'za',
    'Korea Republic': 'kr',
    'Czechia': 'cz',
    'Canada': 'ca',
    'Bosnia and Herzegovina': 'ba',
    'Qatar': 'qa',
    'Switzerland': 'ch',
    'Brazil': 'br',
    'Morocco': 'ma',
    'Haiti': 'ht',
    'Scotland': 'gb-sct',
    'USA': 'us',
    'Paraguay': 'py',
    'Australia': 'au',
    'Türkiye': 'tr',
    'Germany': 'de',
    'Curaçao': 'cw',
    "Côte d'Ivoire": 'ci',
    'Ecuador': 'ec',
    'Netherlands': 'nl',
    'Japan': 'jp',
    'Sweden': 'se',
    'Tunisia': 'tn',
    'Belgium': 'be',
    'Egypt': 'eg',
    'IR Iran': 'ir',
    'New Zealand': 'nz',
    'Spain': 'es',
    'Cabo Verde': 'cv',
    'Saudi Arabia': 'sa',
    'Uruguay': 'uy',
    'France': 'fr',
    'Senegal': 'sn',
    'Iraq': 'iq',
    'Norway': 'no',
    'Argentina': 'ar',
    'Algeria': 'dz',
    'Austria': 'at',
    'Jordan': 'jo',
    'Portugal': 'pt',
    'Congo DR': 'cd',
    'Uzbekistan': 'uz',
    'Colombia': 'co',
    'England': 'gb-eng',
    'Croatia': 'hr',
    'Ghana': 'gh',
    'Panama': 'pa',
}

SPANISH_ALIASES = {
    'Mexico': 'México',
    'South Africa': 'Sudáfrica',
    'Korea Republic': 'Corea del Sur',
    'Czechia': 'Chequia',
    'Canada': 'Canadá',
    'Bosnia and Herzegovina': 'Bosnia y Herzegovina',
    'Qatar': 'Qatar',
    'Switzerland': 'Suiza',
    'Brazil': 'Brasil',
    'Morocco': 'Marruecos',
    'Haiti': 'Haití',
    'Scotland': 'Escocia',
    'USA': 'Estados Unidos',
    'Paraguay': 'Paraguay',
    'Australia': 'Australia',
    'Türkiye': 'Turquía',
    'Germany': 'Alemania',
    'Curaçao': 'Curazao',
    "Côte d'Ivoire": 'Costa de Marfil',
    'Ecuador': 'Ecuador',
    'Netherlands': 'Países Bajos',
    'Japan': 'Japón',
    'Sweden': 'Suecia',
    'Tunisia': 'Túnez',
    'Belgium': 'Bélgica',
    'Egypt': 'Egipto',
    'IR Iran': 'Irán',
    'New Zealand': 'Nueva Zelanda',
    'Spain': 'España',
    'Cabo Verde': 'Cabo Verde',
    'Saudi Arabia': 'Arabia Saudita',
    'Uruguay': 'Uruguay',
    'France': 'Francia',
    'Senegal': 'Senegal',
    'Iraq': 'Irak',
    'Norway': 'Noruega',
    'Argentina': 'Argentina',
    'Algeria': 'Argelia',
    'Austria': 'Austria',
    'Jordan': 'Jordania',
    'Portugal': 'Portugal',
    'Congo DR': 'RD Congo',
    'Uzbekistan': 'Uzbekistán',
    'Colombia': 'Colombia',
    'England': 'Inglaterra',
    'Croatia': 'Croacia',
    'Ghana': 'Ghana',
    'Panama': 'Panamá',
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

GROUP_ROUNDS = [
    [(0, 1), (2, 3)],
    [(0, 2), (1, 3)],
    [(0, 3), (1, 2)],
]
GROUP_STAGE_START_UTC = datetime(2026, 6, 11, 19, 0, tzinfo=ZoneInfo('UTC'))

OFFICIAL_GROUP_FIXTURE_OVERRIDES = {
    ('Argentina', 'Algeria'): {
        'kickoff_at': datetime(2026, 6, 17, 1, 0, tzinfo=ZoneInfo('UTC')),
        'venue': 'Kansas City Stadium',
        'venue_timezone': 'America/Chicago',
    },
    ('Argentina', 'Austria'): {
        'kickoff_at': datetime(2026, 6, 22, 17, 0, tzinfo=ZoneInfo('UTC')),
        'venue': 'Dallas Stadium',
        'venue_timezone': 'America/Chicago',
    },
    ('Argentina', 'Jordan'): {
        'kickoff_at': datetime(2026, 6, 28, 2, 0, tzinfo=ZoneInfo('UTC')),
        'venue': 'Dallas Stadium',
        'venue_timezone': 'America/Chicago',
    },
}


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
                    defaults={
                        'name': team_name,
                        'display_name': SPANISH_ALIASES.get(team_name, team_name),
                        'group': group,
                        'flag_code': FLAG_CODES.get(team_name, ''),
                    },
                )

        match_number = 1
        for round_index, round_pairings in enumerate(GROUP_ROUNDS):
            for _group_index, (letter, group) in enumerate(groups):
                teams = [Team.objects.get(fifa_code=f'{letter}{position}') for position in range(1, 5)]
                for home_idx, away_idx in round_pairings:
                    venue, venue_timezone = VENUES[(match_number - 1) % len(VENUES)]
                    slot = match_number - 1
                    kickoff_at = GROUP_STAGE_START_UTC + timedelta(
                        days=(round_index * 7) + ((slot % 24) // 4),
                        hours=(slot % 4) * 3,
                    )
                    override = OFFICIAL_GROUP_FIXTURE_OVERRIDES.get((teams[home_idx].name, teams[away_idx].name))
                    if override:
                        kickoff_at = override['kickoff_at']
                        venue = override['venue']
                        venue_timezone = override['venue_timezone']
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
        knockout_start = datetime(2026, 7, 1, 15, 0)
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
