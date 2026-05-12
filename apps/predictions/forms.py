from django import forms

from .models import Prediction


SCORE_CHOICES = [(score, score) for score in range(0, 11)]


class PredictionForm(forms.ModelForm):
    class Meta:
        model = Prediction
        fields = ['predicted_home_score', 'predicted_away_score']
        labels = {
            'predicted_home_score': 'Goles local',
            'predicted_away_score': 'Goles visitante',
        }
        widgets = {
            'predicted_home_score': forms.Select(choices=SCORE_CHOICES),
            'predicted_away_score': forms.Select(choices=SCORE_CHOICES),
        }
