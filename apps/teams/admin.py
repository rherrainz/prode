from django.contrib import admin

from .models import Team, WorldCupGroup


@admin.register(WorldCupGroup)
class WorldCupGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'created_at']
    search_fields = ['name']
    ordering = ['order']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'fifa_code', 'flag_code', 'group', 'updated_at']
    list_filter = ['group']
    search_fields = ['name', 'fifa_code', 'flag_code']

# Register your models here.
