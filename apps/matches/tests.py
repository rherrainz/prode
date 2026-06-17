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
from apps.matches.services import thesportsdb
from apps.predictions.models import Prediction
from apps.teams.models import Team
from apps.tournaments.models import FriendTournament


class SyncResultsAndRecalculateCommandTests(TestCase):
    def test_command_syncs_results_then_recalculates_predictions(self):
        calls = []

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

        original_sync_results = sync_results_and_recalculate.sync_results
        original_recalculate_predictions = sync_results_and_recalculate.recalculate_predictions
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
            sync_results_and_recalculate.sync_results = original_sync_results
            sync_results_and_recalculate.recalculate_predictions = original_recalculate_predictions

        self.assertEqual(calls, [('sync', 0, 0, sync_results_and_recalculate.date(2026, 6, 11), False), ('recalculate',)])
        self.assertIn('Pronósticos recalculados: 3', output.getvalue())

    def test_dry_run_does_not_recalculate_predictions(self):
        calls = []

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

        original_sync_results = sync_results_and_recalculate.sync_results
        original_recalculate_predictions = sync_results_and_recalculate.recalculate_predictions
        sync_results_and_recalculate.sync_results = fake_sync_results
        sync_results_and_recalculate.recalculate_predictions = fake_recalculate_predictions
        try:
            call_command('sync_results_and_recalculate', '--dry-run', stdout=StringIO())
        finally:
            sync_results_and_recalculate.sync_results = original_sync_results
            sync_results_and_recalculate.recalculate_predictions = original_recalculate_predictions

        self.assertEqual(calls, [('sync', True)])


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
            result = thesportsdb.sync_results(days_back=0, days_forward=0, base_date=date(2026, 6, 15))
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
            result = thesportsdb.sync_results(days_back=0, days_forward=0, base_date=date(2026, 6, 14))
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
            result = thesportsdb.sync_results(days_back=0, days_forward=0, base_date=date(2026, 6, 17))
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
