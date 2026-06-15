from django.db import migrations, models
from django.db.models import Sum
from django.utils import timezone


def initialize_leaderboard_positions(apps, schema_editor):
    friend_tournament = apps.get_model('tournaments', 'FriendTournament')
    prediction = apps.get_model('predictions', 'Prediction')
    tournament_membership = apps.get_model('tournaments', 'TournamentMembership')
    now = timezone.now()

    for tournament in friend_tournament.objects.all():
        memberships = list(
            tournament_membership.objects
            .filter(tournament=tournament, is_active=True)
            .order_by('joined_at')
        )
        totals = (
            prediction.objects
            .filter(tournament=tournament)
            .values('user_id')
            .annotate(points=Sum('points'))
        )
        points_by_user = {row['user_id']: row['points'] or 0 for row in totals}
        memberships.sort(key=lambda membership: (-points_by_user.get(membership.user_id, 0), membership.joined_at))
        for position, membership in enumerate(memberships, start=1):
            membership.previous_leaderboard_position = position
            membership.leaderboard_position = position
            membership.leaderboard_position_updated_at = now
            membership.save(update_fields=[
                'previous_leaderboard_position',
                'leaderboard_position',
                'leaderboard_position_updated_at',
            ])


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0002_friendtournament_max_members'),
    ]

    operations = [
        migrations.AddField(
            model_name='tournamentmembership',
            name='leaderboard_position',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tournamentmembership',
            name='leaderboard_position_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tournamentmembership',
            name='previous_leaderboard_position',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(initialize_leaderboard_positions, migrations.RunPython.noop),
    ]
