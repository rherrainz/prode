from django.db import models


class Match(models.Model):
    class Phase(models.TextChoices):
        GROUP_STAGE = 'group_stage', 'Fase de grupos'
        ROUND_OF_32 = 'round_of_32', '16avos de final'
        ROUND_OF_16 = 'round_of_16', 'Octavos de final'
        QUARTER_FINAL = 'quarter_final', 'Cuartos de final'
        SEMI_FINAL = 'semi_final', 'Semifinal'
        THIRD_PLACE = 'third_place', 'Tercer puesto'
        FINAL = 'final', 'Final'

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Programado'
        LIVE = 'live', 'En vivo'
        FINISHED = 'finished', 'Finalizado'
        POSTPONED = 'postponed', 'Postergado'
        CANCELLED = 'cancelled', 'Cancelado'

    external_id = models.CharField(max_length=80, blank=True, unique=True, null=True)
    match_number = models.PositiveSmallIntegerField(unique=True)
    phase = models.CharField(max_length=30, choices=Phase.choices)
    group = models.ForeignKey('teams.WorldCupGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='matches')
    home_team = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='home_matches')
    away_team = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='away_matches')
    home_team_placeholder = models.CharField(max_length=120, blank=True)
    away_team_placeholder = models.CharField(max_length=120, blank=True)
    kickoff_at = models.DateTimeField()
    venue = models.CharField(max_length=160, blank=True)
    venue_timezone = models.CharField(max_length=80, default='UTC')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    winner = models.ForeignKey('teams.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='won_matches')
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kickoff_at', 'match_number']

    def __str__(self):
        return f'Partido {self.match_number}'

    @property
    def home_label(self):
        return self.home_team.name if self.home_team else self.home_team_placeholder or 'TBD'

    @property
    def away_label(self):
        return self.away_team.name if self.away_team else self.away_team_placeholder or 'TBD'

    @property
    def has_result(self):
        return self.home_score is not None and self.away_score is not None

    @property
    def score_label(self):
        if not self.has_result:
            return '-'
        return f'{self.home_score} - {self.away_score}'

    def outcome(self):
        if not self.has_result:
            return None
        if self.home_score > self.away_score:
            return 'home'
        if self.away_score > self.home_score:
            return 'away'
        return 'draw'


class ApiSyncLog(models.Model):
    provider = models.CharField(max_length=80)
    endpoint = models.CharField(max_length=200)
    status = models.CharField(max_length=40)
    request_count = models.PositiveIntegerField(default=0)
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.provider} {self.endpoint} {self.status}'

# Create your models here.
