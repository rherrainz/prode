from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.matches.models import Match
from apps.predictions.forms import PredictionForm
from apps.predictions.models import Prediction

from .forms import JoinTournamentForm, StaffTournamentForm
from .models import FriendTournament, TournamentMembership
from .services import join_tournament_by_code, leaderboard_for_tournament, user_is_member


def _member_tournament_or_forbidden(request, slug):
    tournament = get_object_or_404(FriendTournament, slug=slug)
    if not user_is_member(request.user, tournament):
        messages.error(request, 'No tenés permiso para ver este torneo.')
        return None
    return tournament


@login_required
def tournament_list(request):
    memberships = (
        TournamentMembership.objects.filter(user=request.user, is_active=True)
        .select_related('tournament')
        .order_by('tournament__name')
    )
    return render(request, 'tournaments/list.html', {'memberships': memberships})


@login_required
def join_tournament(request):
    if request.method == 'POST':
        form = JoinTournamentForm(request.POST)
        if form.is_valid():
            tournament, status = join_tournament_by_code(request.user, form.cleaned_data['invite_code'])
            if status == 'invalid':
                messages.error(request, 'Código inválido')
            elif status == 'inactive':
                messages.error(request, 'Torneo inactivo')
            elif status == 'full':
                messages.error(request, 'El torneo ya alcanzó el máximo de 15 participantes.')
            else:
                if status == 'already_member':
                    messages.success(request, 'Ya sos parte de este torneo')
                return redirect(tournament)
    else:
        form = JoinTournamentForm()
    return render(request, 'tournaments/join.html', {'form': form})


@staff_member_required
def staff_tournament_admin(request):
    if request.method == 'POST':
        form = StaffTournamentForm(request.POST)
        if form.is_valid():
            tournament = form.save()
            messages.success(request, f'Torneo creado. Código: {tournament.invite_code}')
            return redirect('tournaments:staff_admin')
    else:
        form = StaffTournamentForm()

    tournaments = (
        FriendTournament.objects.select_related('owner')
        .prefetch_related('memberships')
        .order_by('-created_at')
    )
    return render(request, 'tournaments/staff_admin.html', {'form': form, 'tournaments': tournaments})


@staff_member_required
def staff_toggle_tournament_active(request, slug):
    tournament = get_object_or_404(FriendTournament, slug=slug)
    if request.method != 'POST':
        return redirect('tournaments:staff_admin')
    tournament.is_active = not tournament.is_active
    tournament.save(update_fields=['is_active', 'updated_at'])
    status = 'activado' if tournament.is_active else 'desactivado'
    messages.success(request, f'Torneo {status}.')
    return redirect('tournaments:staff_admin')


@login_required
def tournament_detail(request, slug):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    upcoming_matches = Match.objects.filter(kickoff_at__gte=timezone.now()).order_by('kickoff_at', 'match_number')[:5]
    return render(request, 'tournaments/detail.html', {'tournament': tournament, 'upcoming_matches': upcoming_matches})


@login_required
def fixture(request, slug):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    predictions = Prediction.objects.filter(tournament=tournament, user=request.user)
    prediction_by_match = {prediction.match_id: prediction for prediction in predictions}
    matches = Match.objects.select_related('home_team', 'away_team', 'group').order_by('match_number')
    return render(request, 'tournaments/fixture.html', {
        'tournament': tournament,
        'matches': matches,
        'prediction_by_match': prediction_by_match,
    })


@login_required
def match_detail(request, slug, match_id):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team', 'group'), pk=match_id)
    prediction = Prediction.objects.filter(tournament=tournament, user=request.user, match=match).first()
    locked = timezone.now() >= match.kickoff_at

    if request.method == 'POST':
        if locked:
            messages.error(request, 'Pronóstico bloqueado')
            return redirect('tournaments:match_detail', slug=tournament.slug, match_id=match.id)
        form = PredictionForm(request.POST, instance=prediction)
        if form.is_valid():
            prediction = form.save(commit=False)
            prediction.tournament = tournament
            prediction.user = request.user
            prediction.match = match
            prediction.save()
            messages.success(request, 'Pronóstico guardado.')
            return redirect('tournaments:predictions', slug=tournament.slug)
    else:
        form = PredictionForm(instance=prediction)

    return render(request, 'matches/detail.html', {
        'tournament': tournament,
        'match': match,
        'prediction': prediction,
        'form': form,
        'locked': locked,
    })


@login_required
def my_predictions(request, slug):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    predictions = (
        Prediction.objects.filter(tournament=tournament, user=request.user)
        .select_related('match', 'match__home_team', 'match__away_team')
        .order_by('match__match_number')
    )
    return render(request, 'predictions/list.html', {'tournament': tournament, 'predictions': predictions})


@login_required
def leaderboard(request, slug):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    return render(request, 'leaderboard/detail.html', {'tournament': tournament, 'rows': leaderboard_for_tournament(tournament)})


@login_required
def members(request, slug):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    memberships = TournamentMembership.objects.filter(tournament=tournament, is_active=True).select_related('user')
    return render(request, 'tournaments/members.html', {'tournament': tournament, 'memberships': memberships})

# Create your views here.
