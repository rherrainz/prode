import csv
from datetime import datetime

from django.conf import settings
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

SCHEDULE_CSV_PATH = settings.BASE_DIR / 'apps' / 'matches' / 'data' / 'world_cup_2026_schedule.csv'

SCHEDULE_TEAM_NAMES = {
    'Bosnia & Herzegovina': 'Bosnia and Herzegovina',
    'Cape Verde': 'Cabo Verde',
    'DR Congo': 'Congo DR',
    'Iran': 'IR Iran',
    'Ivory Coast': "Côte d'Ivoire",
    'South Korea': 'Korea Republic',
    'United States': 'USA',
}

VENUE_TIMEZONES_BY_CITY = {
    'Arlington': 'America/Chicago',
    'Atlanta': 'America/New_York',
    'East Rutherford': 'America/New_York',
    'Foxborough': 'America/New_York',
    'Guadalajara': 'America/Mexico_City',
    'Houston': 'America/Chicago',
    'Inglewood': 'America/Los_Angeles',
    'Kansas City': 'America/Chicago',
    'Mexico City': 'America/Mexico_City',
    'Miami Gardens': 'America/New_York',
    'Monterrey': 'America/Mexico_City',
    'Philadelphia': 'America/New_York',
    'Santa Clara': 'America/Los_Angeles',
    'Seattle': 'America/Los_Angeles',
    'Toronto': 'America/Toronto',
    'Vancouver': 'America/Vancouver',
}

ROUND_PHASES = {
    'Round of 32': Match.Phase.ROUND_OF_32,
    'Round of 16': Match.Phase.ROUND_OF_16,
    'Quarter-final': Match.Phase.QUARTER_FINAL,
    'Semi-final': Match.Phase.SEMI_FINAL,
    'Third Place': Match.Phase.THIRD_PLACE,
    'Final': Match.Phase.FINAL,
}


def team_name_from_schedule(name):
    return SCHEDULE_TEAM_NAMES.get(name, name)


def kickoff_from_schedule(row):
    return datetime.fromisoformat(f"{row['Date (UTC)']}T{row['Kickoff (UTC)']}:00+00:00")


def phase_from_schedule(round_name):
    if round_name.startswith('Group '):
        return Match.Phase.GROUP_STAGE
    return ROUND_PHASES[round_name]


def schedule_rows():
    with SCHEDULE_CSV_PATH.open(newline='', encoding='utf-8-sig') as schedule_file:
        return list(csv.DictReader(schedule_file))


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

        for row in schedule_rows():
            match_number = int(row['Match'])
            round_name = row['Group / Round']
            phase = phase_from_schedule(round_name)
            group = WorldCupGroup.objects.get(name=round_name) if phase == Match.Phase.GROUP_STAGE else None
            home_name = team_name_from_schedule(row['Team A'])
            away_name = team_name_from_schedule(row['Team B'])
            home_team = Team.objects.filter(name=home_name).first() if home_name != 'TBD' else None
            away_team = Team.objects.filter(name=away_name).first() if away_name != 'TBD' else None
            venue_timezone = VENUE_TIMEZONES_BY_CITY[row['City']]
            Match.objects.update_or_create(
                match_number=match_number,
                defaults={
                    'phase': phase,
                    'group': group,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_team_placeholder': '' if home_team else f'{round_name} equipo local',
                    'away_team_placeholder': '' if away_team else f'{round_name} equipo visitante',
                    'kickoff_at': kickoff_from_schedule(row),
                    'venue': row['Venue'],
                    'venue_timezone': venue_timezone,
                },
            )

        self.stdout.write(self.style.SUCCESS('Estructura sembrada: 12 grupos sorteados, 48 equipos, 104 partidos con zona horaria de sede.'))
