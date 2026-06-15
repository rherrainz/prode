from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.text import slugify


def generate_invite_code():
    return get_random_string(8).upper()


class FriendTournament(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_tournaments')
    description = models.TextField(blank=True)
    invite_code = models.CharField(max_length=20, unique=True, blank=True)
    max_members = models.PositiveSmallIntegerField(default=15)
    is_private = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.invite_code:
            code = generate_invite_code()
            while FriendTournament.objects.filter(invite_code=code).exclude(pk=self.pk).exists():
                code = generate_invite_code()
            self.invite_code = code
        if not self.slug:
            base_slug = slugify(self.name) or 'torneo'
            slug = base_slug
            counter = 2
            while FriendTournament.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('tournaments:detail', kwargs={'slug': self.slug})

    @property
    def active_member_count(self):
        return self.memberships.filter(is_active=True).count()

    @property
    def has_available_slots(self):
        return self.active_member_count < self.max_members


class TournamentMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Dueño'
        ADMIN = 'admin', 'Admin'
        PLAYER = 'player', 'Jugador'

    tournament = models.ForeignKey(FriendTournament, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tournament_memberships')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PLAYER)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    previous_leaderboard_position = models.PositiveSmallIntegerField(null=True, blank=True)
    leaderboard_position = models.PositiveSmallIntegerField(null=True, blank=True)
    leaderboard_position_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(fields=['tournament', 'user'], name='unique_tournament_membership'),
        ]

    def __str__(self):
        return f'{self.user} en {self.tournament}'

# Create your models here.
