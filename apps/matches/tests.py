from io import StringIO
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.matches.admin import MatchAdmin, mark_finished
from apps.matches.management.commands import sync_results_and_recalculate
from apps.matches.models import Match
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
