from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.predictions.models import Prediction

from .models import FriendTournament, TournamentMembership


def user_is_member(user, tournament):
    if not user.is_authenticated:
        return False
    return TournamentMembership.objects.filter(tournament=tournament, user=user, is_active=True).exists()


def get_tournament_for_member(slug, user):
    tournament = get_object_or_404(FriendTournament, slug=slug)
    if not user_is_member(user, tournament):
        return None
    return tournament


def join_tournament_by_code(user, invite_code):
    code = invite_code.strip().upper()
    try:
        tournament = FriendTournament.objects.get(invite_code__iexact=code)
    except FriendTournament.DoesNotExist:
        return None, 'invalid'
    if not tournament.is_active:
        return tournament, 'inactive'
    membership = TournamentMembership.objects.filter(tournament=tournament, user=user).first()
    if membership:
        if not membership.is_active and not tournament.has_available_slots:
            return tournament, 'full'
        if not membership.is_active:
            membership.is_active = True
            membership.save(update_fields=['is_active'])
        return tournament, 'already_member'
    if not tournament.has_available_slots:
        return tournament, 'full'
    TournamentMembership.objects.create(
        tournament=tournament,
        user=user,
        role=TournamentMembership.Role.PLAYER,
    )
    return tournament, 'joined'


def leaderboard_for_tournament(tournament):
    memberships = TournamentMembership.objects.filter(tournament=tournament, is_active=True).select_related('user')
    totals = Prediction.objects.filter(tournament=tournament).values('user_id').annotate(points=Sum('points'))
    points_by_user = {row['user_id']: row['points'] or 0 for row in totals}
    rows = [
        {
            'membership': membership,
            'user': membership.user,
            'points': points_by_user.get(membership.user_id, 0),
            'joined_at': membership.joined_at,
            'previous_position': membership.previous_leaderboard_position,
        }
        for membership in memberships
    ]
    rows.sort(key=lambda row: (-row['points'], row['joined_at']))
    for index, row in enumerate(rows, start=1):
        row['position'] = index
        previous_position = row['previous_position'] or index
        row['position_change'] = previous_position - index
    return rows


def update_leaderboard_positions(tournament):
    now = timezone.now()
    rows = leaderboard_for_tournament(tournament)
    for row in rows:
        membership = row['membership']
        previous_position = membership.leaderboard_position or row['position']
        membership.previous_leaderboard_position = previous_position
        membership.leaderboard_position = row['position']
        membership.leaderboard_position_updated_at = now
        membership.save(update_fields=[
            'previous_leaderboard_position',
            'leaderboard_position',
            'leaderboard_position_updated_at',
        ])
    return len(rows)
