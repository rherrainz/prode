from django.contrib import admin

from apps.predictions.services import recalculate_predictions

from .models import ApiSyncLog, Match


@admin.action(description='Marcar partidos seleccionados como finalizados')
def mark_finished(modeladmin, request, queryset):
    queryset.update(status=Match.Status.FINISHED)


@admin.action(description='Recalcular pronósticos de partidos seleccionados')
def recalculate_selected_matches(modeladmin, request, queryset):
    total = 0
    for match in queryset:
        total += recalculate_predictions(match=match)
    modeladmin.message_user(request, f'Se recalcularon {total} pronósticos.')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['match_number', 'phase', 'group', 'home_team', 'away_team', 'kickoff_at', 'venue', 'venue_timezone', 'status', 'score']
    list_filter = ['phase', 'group', 'status', 'venue_timezone']
    search_fields = ['match_number', 'home_team__name', 'away_team__name', 'home_team_placeholder', 'away_team_placeholder', 'venue']
    actions = [mark_finished, recalculate_selected_matches]

    @admin.display(description='Resultado')
    def score(self, obj):
        return obj.score_label


@admin.register(ApiSyncLog)
class ApiSyncLogAdmin(admin.ModelAdmin):
    list_display = ['provider', 'endpoint', 'status', 'request_count', 'response_code', 'created_at']
    list_filter = ['provider', 'status']
    search_fields = ['endpoint', 'message']
    readonly_fields = ['created_at']

# Register your models here.
