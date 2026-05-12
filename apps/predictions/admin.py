from django.contrib import admin

from .models import Prediction
from .services import recalculate_predictions


@admin.action(description='Recalcular pronósticos seleccionados')
def recalculate_selected_predictions(modeladmin, request, queryset):
    count = 0
    for prediction in queryset.select_related('match'):
        prediction.calculate_points(save=True)
        count += 1
    modeladmin.message_user(request, f'Se recalcularon {count} pronósticos.')


@admin.action(description='Recalcular todos los pronósticos')
def recalculate_all_predictions(modeladmin, request, queryset):
    count = recalculate_predictions()
    modeladmin.message_user(request, f'Se recalcularon {count} pronósticos.')


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'user', 'match', 'predicted_score', 'points', 'calculated_at']
    list_filter = ['tournament', 'user', 'match']
    search_fields = ['tournament__name', 'user__username']
    actions = [recalculate_selected_predictions, recalculate_all_predictions]

    @admin.display(description='Pronóstico')
    def predicted_score(self, obj):
        return obj.score_label

# Register your models here.
