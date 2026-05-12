from django.db import models


class WorldCupGroup(models.Model):
    name = models.CharField(max_length=80, unique=True)
    order = models.PositiveSmallIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=120)
    fifa_code = models.CharField(max_length=10, blank=True)
    group = models.ForeignKey(WorldCupGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')
    flag_code = models.CharField(max_length=12, blank=True)
    flag_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['fifa_code'], condition=~models.Q(fifa_code=''), name='unique_non_empty_fifa_code'),
        ]

    def __str__(self):
        return self.name

# Create your models here.
