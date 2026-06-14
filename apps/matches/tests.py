from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.matches.management.commands import sync_results_and_recalculate


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
