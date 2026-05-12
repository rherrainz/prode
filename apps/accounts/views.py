from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegisterForm, TimezoneForm
from .models import UserProfile


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Cuenta creada correctamente.')
            return redirect('tournaments:list')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def timezone_settings(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = TimezoneForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Zona horaria actualizada.')
            return redirect('tournaments:list')
    else:
        form = TimezoneForm(instance=profile)
    return render(request, 'accounts/timezone.html', {'form': form})

# Create your views here.
