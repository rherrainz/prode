from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.matches.models import Match
from apps.matches.services.fifa import sync_fixture
from apps.matches.services.thesportsdb import sync_results
from apps.predictions.forms import PredictionForm
from apps.predictions.models import Prediction
from apps.predictions.services import recalculate_predictions

from .forms import JoinTournamentForm, StaffTournamentForm
from .models import FriendTournament, TournamentMembership
from .services import join_tournament_by_code, leaderboard_for_tournament, user_is_member


SCORE_CHOICES = range(0, 11)
User = get_user_model()


def _prediction_round_label(match):
    if match.phase == Match.Phase.GROUP_STAGE:
        if match.match_number <= 24:
            return 'Ronda 1'
        if match.match_number <= 48:
            return 'Ronda 2'
        return 'Ronda 3'
    return match.get_phase_display()


def _prediction_rounds(matches, predictions_by_match):
    now = timezone.now()
    rounds = []
    current_label = None
    current_matches = []
    for match in matches:
        label = _prediction_round_label(match)
        if label != current_label:
            if current_matches:
                rounds.append({'label': current_label, 'matches': current_matches})
            current_label = label
            current_matches = []
        current_matches.append({
            'match': match,
            'prediction': predictions_by_match.get(match.id),
            'locked': now >= match.kickoff_at,
        })
    if current_matches:
        rounds.append({'label': current_label, 'matches': current_matches})
    return rounds


def _readonly_prediction_rounds(predictions):
    rounds = []
    current_label = None
    current_predictions = []
    for prediction in predictions:
        label = _prediction_round_label(prediction.match)
        if label != current_label:
            if current_predictions:
                rounds.append({'label': current_label, 'predictions': current_predictions})
            current_label = label
            current_predictions = []
        current_predictions.append(prediction)
    if current_predictions:
        rounds.append({'label': current_label, 'predictions': current_predictions})
    return rounds


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


@staff_member_required
def staff_update_fixture(request):
    if request.method != 'POST':
        return redirect('tournaments:staff_admin')
    try:
        call_command('seed_worldcup_structure')
    except Exception as exc:
        messages.error(request, f'No se pudo actualizar el fixture: {exc}')
    else:
        messages.success(request, 'Fixture actualizado correctamente: 12 grupos, 48 equipos y 104 partidos.')
    return redirect('tournaments:staff_admin')


@staff_member_required
def staff_sync_results(request):
    if request.method != 'POST':
        return redirect('tournaments:staff_admin')
    try:
        fixture_result = sync_fixture(days_back=1, days_forward=14)
        result = sync_results(days_back=1, days_forward=1)
        recalculated = recalculate_predictions()
    except Exception as exc:
        messages.error(request, f'No se pudieron traer los resultados: {exc}')
    else:
        messages.success(
            request,
            f"Fixture FIFA: {fixture_result['fixture_updated_count']} cruces actualizados. "
            f"Resultados sincronizados: {result['updated_count']} partidos actualizados, "
            f"{result['seen_count']} eventos vistos, {recalculated} pronósticos recalculados.",
        )
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
def match_predictions(request, slug, match_id):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team', 'group'), pk=match_id)
    if match.status != Match.Status.FINISHED or not match.has_result:
        return HttpResponseForbidden('Los pronósticos del grupo se muestran cuando el partido ya tiene resultado.')

    memberships = (
        TournamentMembership.objects
        .filter(tournament=tournament, is_active=True)
        .select_related('user')
        .order_by('user__username')
    )
    predictions = (
        Prediction.objects
        .filter(tournament=tournament, match=match)
        .select_related('user')
    )
    predictions_by_user = {prediction.user_id: prediction for prediction in predictions}
    rows = [
        {
            'user': membership.user,
            'prediction': predictions_by_user.get(membership.user_id),
        }
        for membership in memberships
    ]

    return render(request, 'matches/predictions.html', {
        'tournament': tournament,
        'match': match,
        'rows': rows,
    })


@login_required
def my_predictions(request, slug):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    matches = list(
        Match.objects.select_related('home_team', 'away_team', 'group')
        .order_by('match_number')
    )
    predictions = Prediction.objects.filter(tournament=tournament, user=request.user).select_related('match')
    predictions_by_match = {prediction.match_id: prediction for prediction in predictions}

    if request.method == 'POST':
        saved_count = 0
        locked_count = 0
        now = timezone.now()
        for match in matches:
            home_key = f'match_{match.id}_home'
            away_key = f'match_{match.id}_away'
            home_score = request.POST.get(home_key)
            away_score = request.POST.get(away_key)
            if home_score == '' or away_score == '' or home_score is None or away_score is None:
                continue
            if now >= match.kickoff_at:
                locked_count += 1
                continue
            try:
                home_score_int = int(home_score)
                away_score_int = int(away_score)
            except ValueError:
                messages.error(request, 'Hay pronósticos con valores inválidos.')
                return redirect('tournaments:predictions', slug=tournament.slug)
            if home_score_int not in SCORE_CHOICES or away_score_int not in SCORE_CHOICES:
                messages.error(request, 'Los goles deben estar entre 0 y 10.')
                return redirect('tournaments:predictions', slug=tournament.slug)
            Prediction.objects.update_or_create(
                tournament=tournament,
                user=request.user,
                match=match,
                defaults={
                    'predicted_home_score': home_score_int,
                    'predicted_away_score': away_score_int,
                },
            )
            saved_count += 1
        if saved_count:
            messages.success(request, f'Se guardaron {saved_count} pronósticos.')
        if locked_count:
            messages.warning(request, f'{locked_count} partidos ya estaban bloqueados.')
        return redirect('tournaments:predictions', slug=tournament.slug)

    rounds = _prediction_rounds(matches, predictions_by_match)
    return render(request, 'predictions/list.html', {
        'tournament': tournament,
        'rounds': rounds,
        'score_choices': SCORE_CHOICES,
    })


@login_required
def leaderboard(request, slug):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    return render(request, 'leaderboard/detail.html', {'tournament': tournament, 'rows': leaderboard_for_tournament(tournament)})


@login_required
def member_predictions(request, slug, user_id):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')

    viewed_user = get_object_or_404(User, pk=user_id)
    if not TournamentMembership.objects.filter(tournament=tournament, user=viewed_user, is_active=True).exists():
        return HttpResponseForbidden('Ese usuario no participa en este torneo.')

    predictions = (
        Prediction.objects.filter(tournament=tournament, user=viewed_user)
        .select_related('match', 'match__home_team', 'match__away_team', 'match__group')
        .order_by('match__match_number')
    )
    can_view_future = request.user.is_staff
    if not can_view_future:
        predictions = predictions.filter(
            match__status=Match.Status.FINISHED,
            match__home_score__isnull=False,
            match__away_score__isnull=False,
            calculated_at__isnull=False,
        )

    return render(request, 'predictions/member_detail.html', {
        'tournament': tournament,
        'viewed_user': viewed_user,
        'rounds': _readonly_prediction_rounds(predictions),
        'can_view_future': can_view_future,
    })


@login_required
def members(request, slug):
    tournament = _member_tournament_or_forbidden(request, slug)
    if tournament is None:
        return HttpResponseForbidden('No tenés permiso para ver este torneo.')
    memberships = TournamentMembership.objects.filter(tournament=tournament, is_active=True).select_related('user')
    return render(request, 'tournaments/members.html', {'tournament': tournament, 'memberships': memberships})

# Create your views here.
