from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    TIMEZONE_CHOICES = [
        ('America/Buenos_Aires', 'Argentina'),
        ('America/Mexico_City', 'Ciudad de México'),
        ('America/Toronto', 'Toronto / Este'),
        ('America/New_York', 'Nueva York / Este'),
        ('America/Chicago', 'Centro USA'),
        ('America/Denver', 'Montaña USA'),
        ('America/Los_Angeles', 'Pacífico USA'),
        ('America/Vancouver', 'Vancouver'),
        ('Europe/Madrid', 'España'),
        ('UTC', 'UTC'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    timezone = models.CharField(max_length=80, choices=TIMEZONE_CHOICES, default='America/Buenos_Aires')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Perfil de {self.user}'
