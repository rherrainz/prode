from django import forms

from .models import FriendTournament


class JoinTournamentForm(forms.Form):
    invite_code = forms.CharField(label='Código de invitación', max_length=20)


class StaffTournamentForm(forms.ModelForm):
    class Meta:
        model = FriendTournament
        fields = ['name', 'owner', 'description', 'max_members', 'is_private', 'is_active']
        labels = {
            'name': 'Nombre',
            'owner': 'Dueño',
            'description': 'Descripción',
            'max_members': 'Máximo de participantes',
            'is_private': 'Privado',
            'is_active': 'Activo',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'max_members': forms.NumberInput(attrs={'min': 1, 'max': 15}),
        }

    def clean_max_members(self):
        max_members = self.cleaned_data['max_members']
        if max_members > 15:
            raise forms.ValidationError('El máximo permitido es 15 participantes.')
        return max_members
