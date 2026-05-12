from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Prediction(models.Model):
    tournament = models.ForeignKey('tournaments.FriendTournament', on_delete=models.CASCADE, related_name='predictions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='predictions')
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='predictions')
    predicted_home_score = models.PositiveSmallIntegerField()
    predicted_away_score = models.PositiveSmallIntegerField()
    points = models.PositiveSmallIntegerField(default=0)
    calculated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['match__kickoff_at']
        constraints = [
            models.UniqueConstraint(fields=['tournament', 'user', 'match'], name='unique_prediction_per_tournament_user_match'),
        ]

    def __str__(self):
        return f'{self.user} - {self.tournament} - Partido {self.match_id}'

    @property
    def score_label(self):
        return f'{self.predicted_home_score} - {self.predicted_away_score}'

    @property
    def is_locked(self):
        return timezone.now() >= self.match.kickoff_at

    def clean(self):
        if self.match_id and self.pk is None and timezone.now() >= self.match.kickoff_at:
            raise ValidationError('No se puede pronosticar un partido que ya empezó.')

    def predicted_outcome(self):
        if self.predicted_home_score > self.predicted_away_score:
            return 'home'
        if self.predicted_away_score > self.predicted_home_score:
            return 'away'
        return 'draw'

    def calculate_points(self, save=True):
        if self.match.status != 'finished' or not self.match.has_result:
            self.points = 0
            self.calculated_at = None
        elif self.predicted_home_score == self.match.home_score and self.predicted_away_score == self.match.away_score:
            self.points = 5
            self.calculated_at = timezone.now()
        elif self.predicted_outcome() == self.match.outcome():
            self.points = 2
            self.calculated_at = timezone.now()
        else:
            self.points = 0
            self.calculated_at = timezone.now()
        if save:
            self.save(update_fields=['points', 'calculated_at', 'updated_at'])
        return self.points

# Create your models here.
