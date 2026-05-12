from django import forms

from .models import Prediction


class PredictionForm(forms.ModelForm):
    class Meta:
        model = Prediction
        fields = ['predicted_home_score', 'predicted_away_score']
        labels = {
            'predicted_home_score': 'Goles local',
            'predicted_away_score': 'Goles visitante',
        }
        widgets = {
            'predicted_home_score': forms.NumberInput(attrs={'min': 0}),
            'predicted_away_score': forms.NumberInput(attrs={'min': 0}),
        }
