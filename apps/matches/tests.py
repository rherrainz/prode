from io import StringIO
from datetime import date, datetime, timedelta, timezone as datetime_timezone

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.matches.admin import MatchAdmin, mark_finished
from apps.matches.management.commands import sync_results_and_recalculate
from apps.matches.models import Match
from apps.matches.services import fifa, thesportsdb
from apps.predictions.models import Prediction
from apps.teams.models import Team
from apps.tournaments.models import FriendTournament


class SyncResultsAndRecalculateCommandTests(TestCase):
    def test_command_syncs_results_then_recalculates_predictions(self):
        calls = []

        def fake_sync_fixture(days_back, days_forward, base_date, dry_run):
            calls.append(('fixture', days_back, days_forward, base_date, dry_run))
            return {
                'request_count': 1,
                'seen_count': 2,
                'updated_count': 0,
                'fixture_updated_count': 1,
            }

        def fake_sync_results(days_back, days_forward, base_date, dry_run):
            calls.append(('sync', days_back, days_forward, base_date, dry_run))
            return {
                'request_count': 1,
                'seen_count': 2,
                'updated_count': 1,
            }

        def fake_recalculate_predictions():
            calls.append(('recalculate',))
            return 3

        original_sync_fixture = sync_results_and_recalculate.sync_fixture
        original_sync_results = sync_results_and_recalculate.sync_results
        original_recalculate_predictions = sync_results_and_recalculate.recalculate_predictions
        sync_results_and_recalculate.sync_fixture = fake_sync_fixture
        sync_results_and_recalculate.sync_results = fake_sync_results
        sync_results_and_recalculate.recalculate_predictions = fake_recalculate_predictions
        try:
            output = StringIO()
            call_command(
                'sync_results_and_recalculate',
                '--date',
                '2026-06-11',
                '--days-back',
                '0',
                '--days-forward',
                '0',
                stdout=output,
            )
        finally:
            sync_results_and_recalculate.sync_fixture = original_sync_fixture
            sync_results_and_recalculate.sync_results = original_sync_results
            sync_results_and_recalculate.recalculate_predictions = original_recalculate_predictions

        self.assertEqual(calls, [
            ('fixture', 0, 14, sync_results_and_recalculate.date(2026, 6, 11), False),
            ('sync', 0, 0, sync_results_and_recalculate.date(2026, 6, 11), False),
            ('recalculate',),
        ])
        self.assertIn('Pronósticos recalculados: 3', output.getvalue())

    def test_dry_run_does_not_recalculate_predictions(self):
        calls = []

        def fake_sync_fixture(days_back, days_forward, base_date, dry_run):
            calls.append(('fixture', dry_run))
            return {
                'request_count': 1,
                'seen_count': 2,
                'updated_count': 0,
                'fixture_updated_count': 1,
            }

        def fake_sync_results(days_back, days_forward, base_date, dry_run):
            calls.append(('sync', dry_run))
            return {
                'request_count': 1,
                'seen_count': 2,
                'updated_count': 1,
            }

        def fake_recalculate_predictions():
            calls.append(('recalculate',))
            return 3

        original_sync_fixture = sync_results_and_recalculate.sync_fixture
        original_sync_results = sync_results_and_recalculate.sync_results
        original_recalculate_predictions = sync_results_and_recalculate.recalculate_predictions
        sync_results_and_recalculate.sync_fixture = fake_sync_fixture
        sync_results_and_recalculate.sync_results = fake_sync_results
        sync_results_and_recalculate.recalculate_predictions = fake_recalculate_predictions
        try:
            call_command('sync_results_and_recalculate', '--dry-run', stdout=StringIO())
        finally:
            sync_results_and_recalculate.sync_fixture = original_sync_fixture
            sync_results_and_recalculate.sync_results = original_sync_results
            sync_results_and_recalculate.recalculate_predictions = original_recalculate_predictions

        self.assertEqual(calls, [('fixture', True), ('sync', True)])


class FifaSyncTests(TestCase):
    def test_sync_fixture_populates_confirmed_knockout_match(self):
        south_africa = Team.objects.create(name='South Africa', fifa_code='RSA')
        canada = Team.objects.create(name='Canada', fifa_code='CAN')
        match = Match.objects.create(
            match_number=73,
            phase=Match.Phase.ROUND_OF_32,
            kickoff_at=datetime(2026, 6, 28, 19, 0, tzinfo=datetime_timezone.utc),
            home_team_placeholder='Round of 32 equipo local',
            away_team_placeholder='Round of 32 equipo visitante',
        )

        def fake_fetch_matches(start_at, end_at):
            return 'fifa-fixture-endpoint', [{
                'IdMatch': '400021518',
                'MatchNumber': 73,
                'Date': '2026-06-28T19:00:00Z',
                'Home': {
                    'IdTeam': '43883',
                    'TeamName': [{'Locale': 'en-GB', 'Description': 'South Africa'}],
                },
                'Away': {
                    'IdTeam': '43899',
                    'TeamName': [{'Locale': 'en-GB', 'Description': 'Canada'}],
                },
                'HomeTeamScore': None,
                'AwayTeamScore': None,
                'Stadium': {'Name': [{'Locale': 'en-GB', 'Description': 'Los Angeles Stadium'}]},
            }]

        original_fetch_matches = fifa._fetch_matches
        fifa._fetch_matches = fake_fetch_matches
        try:
            result = fifa.sync_fixture(days_back=0, days_forward=0, base_date=date(2026, 6, 28))
        finally:
            fifa._fetch_matches = original_fetch_matches

        match.refresh_from_db()
        self.assertEqual(result['seen_count'], 1)
        self.assertEqual(result['fixture_updated_count'], 1)
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(match.external_id, 'fifa:400021518')
        self.assertEqual(match.home_team, south_africa)
        self.assertEqual(match.away_team, canada)
        self.assertEqual(match.venue, 'Los Angeles Stadium')
        self.assertEqual(match.status, Match.Status.SCHEDULED)

    def test_sync_fixture_populates_partial_knockout_match(self):
        england = Team.objects.create(name='England', fifa_code='ENG')
        match = Match.objects.create(
            match_number=80,
            phase=Match.Phase.ROUND_OF_32,
            kickoff_at=datetime(2026, 7, 1, 16, 0, tzinfo=datetime_timezone.utc),
            home_team_placeholder='Round of 32 equipo local',
            away_team_placeholder='Round of 32 equipo visitante',
        )

        def fake_fetch_matches(start_at, end_at):
            return 'fifa-fixture-endpoint', [{
                'IdMatch': '400021520',
                'MatchNumber': 80,
                'Date': '2026-07-01T16:00:00Z',
                'Home': {
                    'IdTeam': '43942',
                    'TeamName': [{'Locale': 'en-GB', 'Description': 'England'}],
                },
                'Away': None,
                'HomeTeamScore': None,
                'AwayTeamScore': None,
                'Stadium': {'Name': [{'Locale': 'en-GB', 'Description': 'Atlanta Stadium'}]},
            }]

        original_fetch_matches = fifa._fetch_matches
        fifa._fetch_matches = fake_fetch_matches
        try:
            result = fifa.sync_fixture(days_back=0, days_forward=0, base_date=date(2026, 7, 1))
        finally:
            fifa._fetch_matches = original_fetch_matches

        match.refresh_from_db()
        self.assertEqual(result['fixture_updated_count'], 1)
        self.assertEqual(match.home_team, england)
        self.assertEqual(match.home_team_placeholder, '')
        self.assertIsNone(match.away_team)
        self.assertEqual(match.away_team_placeholder, 'Round of 32 equipo visitante')

    def test_sync_fixture_updates_knockout_winner_placeholders(self):
        match = Match.objects.create(
            match_number=89,
            phase=Match.Phase.ROUND_OF_16,
            kickoff_at=datetime(2026, 7, 4, 21, 0, tzinfo=datetime_timezone.utc),
            home_team_placeholder='Round of 16 equipo local',
            away_team_placeholder='Round of 16 equipo visitante',
        )

        def fake_fetch_matches(start_at, end_at):
            return 'fifa-fixture-endpoint', []

        original_fetch_matches = fifa._fetch_matches
        fifa._fetch_matches = fake_fetch_matches
        try:
            result = fifa.sync_fixture(days_back=0, days_forward=0, base_date=date(2026, 7, 4))
        finally:
            fifa._fetch_matches = original_fetch_matches

        match.refresh_from_db()
        self.assertEqual(result['fixture_updated_count'], 1)
        self.assertEqual(match.home_team_placeholder, 'Ganador partido 73')
        self.assertEqual(match.away_team_placeholder, 'Ganador partido 75')

    def test_sync_results_uses_fifa_fallback_for_missing_result(self):
        south_africa = Team.objects.create(name='South Africa', fifa_code='RSA')
        canada = Team.objects.create(name='Canada', fifa_code='CAN')
        match = Match.objects.create(
            match_number=73,
            phase=Match.Phase.ROUND_OF_32,
            kickoff_at=datetime(2026, 6, 28, 19, 0, tzinfo=datetime_timezone.utc),
            home_team=south_africa,
            away_team=canada,
        )

        def fake_fetch_events_for_day(day):
            return 'fake-endpoint', []

        def fake_fetch_events_for_season():
            return 'fake-season-endpoint', []

        def fake_fetch_events_by_name(home_name, away_name):
            return 'fake-search-endpoint', []

        def fake_fetch_matches(start_at, end_at):
            return 'fifa-results-endpoint', [{
                'IdMatch': '400021518',
                'MatchNumber': 73,
                'Date': '2026-06-28T19:00:00Z',
                'Home': {
                    'IdTeam': '43883',
                    'TeamName': [{'Locale': 'en-GB', 'Description': 'South Africa'}],
                },
                'Away': {
                    'IdTeam': '43899',
                    'TeamName': [{'Locale': 'en-GB', 'Description': 'Canada'}],
                },
                'HomeTeamScore': 1,
                'AwayTeamScore': 1,
                'HomeTeamPenaltyScore': 5,
                'AwayTeamPenaltyScore': 4,
                'Winner': '43883',
                'MatchStatus': 0,
                'Stadium': {'Name': [{'Locale': 'en-GB', 'Description': 'Los Angeles Stadium'}]},
            }]

        original_fetch = thesportsdb._fetch_events_for_day
        original_fetch_season = thesportsdb._fetch_events_for_season
        original_fetch_by_name = thesportsdb._fetch_events_by_name
        original_fetch_matches = fifa._fetch_matches
        thesportsdb._fetch_events_for_day = fake_fetch_events_for_day
        thesportsdb._fetch_events_for_season = fake_fetch_events_for_season
        thesportsdb._fetch_events_by_name = fake_fetch_events_by_name
        fifa._fetch_matches = fake_fetch_matches
        try:
            result = thesportsdb.sync_results(days_back=0, days_forward=0, base_date=date(2026, 6, 28))
        finally:
            thesportsdb._fetch_events_for_day = original_fetch
            thesportsdb._fetch_events_for_season = original_fetch_season
            thesportsdb._fetch_events_by_name = original_fetch_by_name
            fifa._fetch_matches = original_fetch_matches

        match.refresh_from_db()
        self.assertEqual(result['updated_count'], 1)
        self.assertEqual(match.status, Match.Status.FINISHED)
        self.assertEqual(match.home_score, 1)
        self.assertEqual(match.away_score, 1)
        self.assertEqual(match.winner, south_africa)


class TheSportsDBSyncDateTests(TestCase):
    def test_sync_uses_event_timezone_date_for_utc_next_day_matches(self):
        sweden = Team.objects.create(name='Sweden', fifa_code='SWE')
        tunisia = Team.objects.create(name='Tunisia', fifa_code='TUN')
        match = Match.objects.create(
            match_number=12,
            phase=Match.Phase.GROUP_STAGE,
            home_team=sweden,
            away_team=tunisia,
            kickoff_at=datetime(2026, 6, 15, 2, 0, tzinfo=datetime_timezone.utc),
        )
        requested_days = []

        def fake_fetch_events_for_day(day):
            requested_days.append(day)
            if day == date(2026, 6, 14):
                return 'fake-endpoint', [{
                    'idEvent': 'sweden-tunisia',
                    'strHomeTeam': 'Sweden',
                    'strAwayTeam': 'Tunisia',
                    'intHomeScore': '1',
                    'intAwayScore': '0',
                }]
            return 'fake-endpoint', []

        def fake_fetch_events_for_season():
            return 'fake-season-endpoint', []

        def fake_fetch_events_by_name(home_name, away_name):
            return 'fake-search-endpoint', []

        original_fetch = thesportsdb._fetch_events_for_day
        original_fetch_season = thesportsdb._fetch_events_for_season
        original_fetch_by_name = thesportsdb._fetch_events_by_name
        thesportsdb._fetch_events_for_day = fake_fetch_events_for_day
        thesportsdb._fetch_events_for_season = fake_fetch_events_for_season
        thesportsdb._fetch_events_by_name = fake_fetch_events_by_name
        try:
            result = thesportsdb.sync_results(days_back=0, days_forward=0, base_date=date(2026, 6, 15), use_fifa_fallback=False)
        finally:
            thesportsdb._fetch_events_for_day = original_fetch
            thesportsdb._fetch_events_for_season = original_fetch_season
            thesportsdb._fetch_events_by_name = original_fetch_by_name

        match.refresh_from_db()
        self.assertEqual(requested_days, [date(2026, 6, 14), date(2026, 6, 15)])
        self.assertEqual(result['updated_count'], 1)
        self.assertEqual(match.status, Match.Status.FINISHED)
        self.assertEqual(match.home_score, 1)
        self.assertEqual(match.away_score, 0)

    def test_sync_uses_season_fallback_when_eventsday_omits_match(self):
        netherlands = Team.objects.create(name='Netherlands', fifa_code='NED')
        japan = Team.objects.create(name='Japan', fifa_code='JPN')
        match = Match.objects.create(
            match_number=10,
            phase=Match.Phase.GROUP_STAGE,
            home_team=netherlands,
            away_team=japan,
            kickoff_at=datetime(2026, 6, 14, 20, 0, tzinfo=datetime_timezone.utc),
        )

        def fake_fetch_events_for_day(day):
            return 'fake-endpoint', []

        def fake_fetch_events_for_season():
            return 'fake-season-endpoint', [{
                'idEvent': 'netherlands-japan',
                'dateEvent': '2026-06-14',
                'strHomeTeam': 'Netherlands',
                'strAwayTeam': 'Japan',
                'intHomeScore': '2',
                'intAwayScore': '2',
            }]

        def fake_fetch_events_by_name(home_name, away_name):
            return 'fake-search-endpoint', []

        original_fetch = thesportsdb._fetch_events_for_day
        original_fetch_season = thesportsdb._fetch_events_for_season
        original_fetch_by_name = thesportsdb._fetch_events_by_name
        thesportsdb._fetch_events_for_day = fake_fetch_events_for_day
        thesportsdb._fetch_events_for_season = fake_fetch_events_for_season
        thesportsdb._fetch_events_by_name = fake_fetch_events_by_name
        try:
            result = thesportsdb.sync_results(days_back=0, days_forward=0, base_date=date(2026, 6, 14), use_fifa_fallback=False)
        finally:
            thesportsdb._fetch_events_for_day = original_fetch
            thesportsdb._fetch_events_for_season = original_fetch_season
            thesportsdb._fetch_events_by_name = original_fetch_by_name

        match.refresh_from_db()
        self.assertEqual(result['request_count'], 3)
        self.assertEqual(result['seen_count'], 1)
        self.assertEqual(result['updated_count'], 1)
        self.assertEqual(match.status, Match.Status.FINISHED)
        self.assertEqual(match.home_score, 2)
        self.assertEqual(match.away_score, 2)

    def test_sync_uses_search_fallback_when_day_and_season_omit_match(self):
        portugal = Team.objects.create(name='Portugal', fifa_code='POR')
        congo = Team.objects.create(name='Congo DR', fifa_code='COD')
        match = Match.objects.create(
            match_number=21,
            phase=Match.Phase.GROUP_STAGE,
            home_team=portugal,
            away_team=congo,
            kickoff_at=datetime(2026, 6, 17, 17, 0, tzinfo=datetime_timezone.utc),
        )
        searched_names = []

        def fake_fetch_events_for_day(day):
            return 'fake-endpoint', []

        def fake_fetch_events_for_season():
            return 'fake-season-endpoint', []

        def fake_fetch_events_by_name(home_name, away_name):
            searched_names.append((home_name, away_name))
            return 'fake-search-endpoint', [{
                'idEvent': 'portugal-dr-congo',
                'dateEvent': '2026-06-17',
                'strHomeTeam': 'Portugal',
                'strAwayTeam': 'DR Congo',
                'intHomeScore': '1',
                'intAwayScore': '1',
            }]

        original_fetch = thesportsdb._fetch_events_for_day
        original_fetch_season = thesportsdb._fetch_events_for_season
        original_fetch_by_name = thesportsdb._fetch_events_by_name
        thesportsdb._fetch_events_for_day = fake_fetch_events_for_day
        thesportsdb._fetch_events_for_season = fake_fetch_events_for_season
        thesportsdb._fetch_events_by_name = fake_fetch_events_by_name
        try:
            result = thesportsdb.sync_results(days_back=0, days_forward=0, base_date=date(2026, 6, 17), use_fifa_fallback=False)
        finally:
            thesportsdb._fetch_events_for_day = original_fetch
            thesportsdb._fetch_events_for_season = original_fetch_season
            thesportsdb._fetch_events_by_name = original_fetch_by_name

        match.refresh_from_db()
        self.assertEqual(searched_names, [('Portugal', 'Congo DR')])
        self.assertEqual(result['request_count'], 3)
        self.assertEqual(result['seen_count'], 1)
        self.assertEqual(result['updated_count'], 1)
        self.assertEqual(match.external_id, 'thesportsdb:portugal-dr-congo')
        self.assertEqual(match.status, Match.Status.FINISHED)
        self.assertEqual(match.home_score, 1)
        self.assertEqual(match.away_score, 1)

    def test_sync_populates_knockout_match_and_advances_penalty_winner(self):
        south_africa = Team.objects.create(name='South Africa', fifa_code='RSA')
        canada = Team.objects.create(name='Canada', fifa_code='CAN')
        round_of_32 = Match.objects.create(
            match_number=73,
            phase=Match.Phase.ROUND_OF_32,
            kickoff_at=datetime(2026, 6, 28, 19, 0, tzinfo=datetime_timezone.utc),
            home_team_placeholder='Round of 32 equipo local',
            away_team_placeholder='Round of 32 equipo visitante',
        )
        round_of_16 = Match.objects.create(
            match_number=89,
            phase=Match.Phase.ROUND_OF_16,
            kickoff_at=datetime(2026, 7, 4, 17, 0, tzinfo=datetime_timezone.utc),
            home_team_placeholder='Round of 16 equipo local',
            away_team_placeholder='Round of 16 equipo visitante',
        )

        def fake_fetch_events_for_day(day):
            if day == date(2026, 6, 28):
                return 'fake-endpoint', [{
                    'idEvent': 'round-32-73',
                    'dateEvent': '2026-06-28',
                    'strTimestamp': '2026-06-28T19:00:00+00:00',
                    'strHomeTeam': 'South Africa',
                    'strAwayTeam': 'Canada',
                    'intHomeScore': '1',
                    'intAwayScore': '1',
                    'intHomePenaltyScore': '5',
                    'intAwayPenaltyScore': '4',
                }]
            return 'fake-endpoint', []

        def fake_fetch_events_for_season():
            return 'fake-season-endpoint', []

        def fake_fetch_events_by_name(home_name, away_name):
            return 'fake-search-endpoint', []

        original_fetch = thesportsdb._fetch_events_for_day
        original_fetch_season = thesportsdb._fetch_events_for_season
        original_fetch_by_name = thesportsdb._fetch_events_by_name
        thesportsdb._fetch_events_for_day = fake_fetch_events_for_day
        thesportsdb._fetch_events_for_season = fake_fetch_events_for_season
        thesportsdb._fetch_events_by_name = fake_fetch_events_by_name
        try:
            result = thesportsdb.sync_results(days_back=0, days_forward=0, base_date=date(2026, 6, 28), use_fifa_fallback=False)
        finally:
            thesportsdb._fetch_events_for_day = original_fetch
            thesportsdb._fetch_events_for_season = original_fetch_season
            thesportsdb._fetch_events_by_name = original_fetch_by_name

        round_of_32.refresh_from_db()
        round_of_16.refresh_from_db()
        self.assertEqual(result['updated_count'], 1)
        self.assertEqual(result['fixture_updated_count'], 2)
        self.assertEqual(round_of_32.external_id, 'thesportsdb:round-32-73')
        self.assertEqual(round_of_32.home_team, south_africa)
        self.assertEqual(round_of_32.away_team, canada)
        self.assertEqual(round_of_32.home_score, 1)
        self.assertEqual(round_of_32.away_score, 1)
        self.assertEqual(round_of_32.winner, south_africa)
        self.assertEqual(round_of_16.home_team, south_africa)
        self.assertEqual(round_of_16.home_team_placeholder, '')

    def test_sync_populates_confirmed_knockout_fixture_without_result(self):
        canada = Team.objects.create(name='Canada', fifa_code='CAN')
        south_africa = Team.objects.create(name='South Africa', fifa_code='RSA')
        match = Match.objects.create(
            match_number=73,
            phase=Match.Phase.ROUND_OF_32,
            kickoff_at=datetime(2026, 6, 28, 19, 0, tzinfo=datetime_timezone.utc),
            home_team_placeholder='Round of 32 equipo local',
            away_team_placeholder='Round of 32 equipo visitante',
        )

        def fake_fetch_events_for_day(day):
            if day == date(2026, 6, 28):
                return 'fake-endpoint', [{
                    'idEvent': 'canada-south-africa',
                    'dateEvent': '2026-06-28',
                    'strTimestamp': '2026-06-28T19:00:00+00:00',
                    'strHomeTeam': 'Canada',
                    'strAwayTeam': 'South Africa',
                    'intHomeScore': None,
                    'intAwayScore': None,
                }]
            return 'fake-endpoint', []

        def fake_fetch_events_for_season():
            return 'fake-season-endpoint', []

        def fake_fetch_events_by_name(home_name, away_name):
            return 'fake-search-endpoint', []

        original_fetch = thesportsdb._fetch_events_for_day
        original_fetch_season = thesportsdb._fetch_events_for_season
        original_fetch_by_name = thesportsdb._fetch_events_by_name
        thesportsdb._fetch_events_for_day = fake_fetch_events_for_day
        thesportsdb._fetch_events_for_season = fake_fetch_events_for_season
        thesportsdb._fetch_events_by_name = fake_fetch_events_by_name
        try:
            result = thesportsdb.sync_results(days_back=0, days_forward=1, base_date=date(2026, 6, 27), use_fifa_fallback=False)
        finally:
            thesportsdb._fetch_events_for_day = original_fetch
            thesportsdb._fetch_events_for_season = original_fetch_season
            thesportsdb._fetch_events_by_name = original_fetch_by_name

        match.refresh_from_db()
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(result['fixture_updated_count'], 1)
        self.assertEqual(match.external_id, 'thesportsdb:canada-south-africa')
        self.assertEqual(match.home_team, canada)
        self.assertEqual(match.away_team, south_africa)
        self.assertEqual(match.home_team_placeholder, '')
        self.assertEqual(match.away_team_placeholder, '')
        self.assertEqual(match.status, Match.Status.SCHEDULED)
        self.assertIsNone(match.home_score)
        self.assertIsNone(match.away_score)

    def test_semifinal_advancement_populates_final_and_third_place(self):
        argentina = Team.objects.create(name='Argentina', fifa_code='ARG')
        brazil = Team.objects.create(name='Brazil', fifa_code='BRA')
        semifinal = Match.objects.create(
            match_number=101,
            phase=Match.Phase.SEMI_FINAL,
            home_team=argentina,
            away_team=brazil,
            kickoff_at=datetime(2026, 7, 14, 19, 0, tzinfo=datetime_timezone.utc),
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=0,
            winner=argentina,
        )
        third_place = Match.objects.create(
            match_number=103,
            phase=Match.Phase.THIRD_PLACE,
            kickoff_at=datetime(2026, 7, 18, 21, 0, tzinfo=datetime_timezone.utc),
        )
        final = Match.objects.create(
            match_number=104,
            phase=Match.Phase.FINAL,
            kickoff_at=datetime(2026, 7, 19, 19, 0, tzinfo=datetime_timezone.utc),
        )

        from apps.matches.services.knockout import advance_knockout_match

        updated_count = advance_knockout_match(semifinal)

        third_place.refresh_from_db()
        final.refresh_from_db()
        self.assertEqual(updated_count, 2)
        self.assertEqual(final.home_team, argentina)
        self.assertEqual(third_place.home_team, brazil)


class MatchAdminRecalculationTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().post('/admin/matches/match/')
        self.request.user = User.objects.create_superuser('admin', 'admin@example.com', 'pass12345')
        self.match_admin = MatchAdmin(Match, admin.site)
        self.messages = []
        self.match_admin.message_user = lambda request, message, level=None, extra_tags='', fail_silently=False: self.messages.append(message)
        self.home = Team.objects.create(name='Australia', fifa_code='AUS')
        self.away = Team.objects.create(name='Türkiye', fifa_code='TUR')
        self.match = Match.objects.create(
            match_number=8,
            phase=Match.Phase.GROUP_STAGE,
            home_team=self.home,
            away_team=self.away,
            kickoff_at=timezone.now() - timedelta(hours=2),
        )
        self.tournament = FriendTournament.objects.create(name='Test Tournament')
        self.user = User.objects.create_user('player', 'player@example.com', 'pass12345')
        self.prediction = Prediction.objects.create(
            tournament=self.tournament,
            user=self.user,
            match=self.match,
            predicted_home_score=2,
            predicted_away_score=0,
        )

    def test_match_admin_save_recalculates_when_result_changes(self):
        class FakeForm:
            changed_data = ['status', 'home_score', 'away_score']

        self.match.status = Match.Status.FINISHED
        self.match.home_score = 2
        self.match.away_score = 0

        self.match_admin.save_model(self.request, self.match, FakeForm(), change=True)

        self.prediction.refresh_from_db()
        self.assertEqual(self.prediction.points, 5)
        self.assertIsNotNone(self.prediction.calculated_at)
        self.assertEqual(self.messages, ['Se recalcularon 1 pronósticos para este partido.'])

    def test_mark_finished_action_recalculates_existing_scores(self):
        self.match.home_score = 2
        self.match.away_score = 0
        self.match.save(update_fields=['home_score', 'away_score', 'updated_at'])

        mark_finished(self.match_admin, self.request, Match.objects.filter(pk=self.match.pk))

        self.prediction.refresh_from_db()
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.FINISHED)
        self.assertEqual(self.prediction.points, 5)
        self.assertIsNotNone(self.prediction.calculated_at)
